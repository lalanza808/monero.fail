import logging
from datetime import datetime, timedelta
from time import sleep

import geoip2.database
import arrow
import requests
from flask import Blueprint
from urllib.parse import urlparse

from xmrnodes.helpers import determine_crypto, is_onion, is_i2p, make_request
from xmrnodes.helpers import retrieve_peers, rw_cache, get_highest_block, get_geoip
from xmrnodes.models import Node, HealthCheck, Peer
from xmrnodes import config

bp = Blueprint("cli", "cli", cli_group=None)


@bp.cli.command("init")
def init():
    pass


@bp.cli.command("check")
def check_nodes():
    diff = datetime.utcnow() - timedelta(hours=72)
    checks = HealthCheck.select().where(HealthCheck.datetime <= diff)
    for check in checks:
        print("Deleting check", check.id)
        check.delete_instance()
    nodes = Node.select().where(Node.validated == True)
    for node in nodes:
        try:
            check_node(node.url)
        except KeyboardInterrupt:
            exit()


def check_node(_node):
    if _node.startswith("http"):
        node = Node.select().where(Node.url == _node).first()
    else:
        node = Node.select().where(Node.id == _node).first()
    if not node:
        print('node found')
        pass
    now = datetime.utcnow()
    hc = HealthCheck(node=node)
    logging.info(f"Attempting to check {node.url}")
    try:
        r = make_request(node.url)
        assert "status" in r.json()
        assert "offline" in r.json()
        assert "height" in r.json()
        if 'donation_address' in r.json():
            node.donation_address = r.json()['donation_address']
        has_cors = "Access-Control-Allow-Origin" in r.headers
        is_ssl = node.url.startswith("https://")
        if r.json()["status"] == "OK":
            node.web_compatible = has_cors and is_ssl
            node.last_height = r.json()["height"]
            hc.health = True
            highest_block = get_highest_block(node.nettype, node.crypto)
            healthy_block = highest_block - config.HEALTHY_BLOCK_DIFF
            if r.json()["height"] < healthy_block:
                node.available = False
                logging.info("unhealthy")
            else:
                node.available = True
                logging.info("success")
        else:
            raise
    except:
        logging.info("fail")
        node.datetime_failed = now
        node.available = False
        hc.health = False
    finally:
        node.datetime_checked = now
        node.save()
        hc.save()
    if (
        node.get_failed_checks().count() == node.get_all_checks().count()
        and node.get_all_checks().count() > 5
    ):
        print("this node fails all of its health checks - deleting it!")
        for _hc in node.get_all_checks():
            _hc.delete_instance()
        node.delete_instance()

def upsert_peer(peer):
    exists = Peer.select().where(Peer.url == peer).first()
    if exists:
        exists.datetime = datetime.utcnow()
        exists.save()
    else:
        with geoip2.database.Reader("./data/GeoLite2-City.mmdb") as geodb:
            try:
                u = urlparse(peer)
                _url = f"{u.scheme}://{u.netloc}".lower()
                geodata = geodb.city(u.hostname)
                p = Peer(
                    url=_url,
                    country=geodata.country.name,
                    city=geodata.city.name,
                    postal=geodata.postal.code,
                    lat=geodata.location.latitude,
                    lon=geodata.location.longitude,
                )
                p.save()
            except Exception as e:
                pass

def _get_peers():
    """
    This command keeps will go through the oldest nodes and scan them for more peers.
    Unresponsive peers get deleted. Responsive peers get their datestamp refreshed to move
    to the top of the list. It will only crawl a subset of peers and is intended to be
    run in intervals. The script will automatically prune out peers over time.
    """
    # crawl existing peers
    peers = Peer.select().order_by(Peer.datetime.asc()).limit(20)
    for peer in peers:
        try:
            new_peers = retrieve_peers(peer.hostname, peer.port)
            if new_peers:
                new = []
                for new_peer in new_peers:
                    exists = Peer.select().where(Peer.url == new_peer).first()
                    if not exists:
                        new.append(new_peer)
                print(f"+++ Found {len(new)} more peers from {peer.url}")
                upsert_peer(peer.url)
                for new_peer in new_peers:
                    upsert_peer(new_peer)
            else:
                raise Exception('dead node')
        except Exception as e:
            print(f"--- Dead peer {peer.url}")
            peer.delete_instance()

    # if no peers are available in the database then get a list of peers to scan from upstream node
    if not peers:
        print(f"[.] Retrieving peers from {config.NODE_HOST}:{config.NODE_PORT}")
        peers_to_scan = retrieve_peers(config.NODE_HOST, config.NODE_PORT)
        print(f"[+] Found {len(peers_to_scan)} initial peers to begin scraping.")
        for peer in peers_to_scan:
            upsert_peer(peer)
    
    # rw_cache("map_peers", list(Peer.select().execute()))

@bp.cli.command("get_peers")
def get_peers():
    try:
        _get_peers()
    except KeyboardInterrupt:
        print("Stopped")
    except Exception as e:
        print(f"Error: {e}")

@bp.cli.command("validate")
def validate():
    nodes = Node.select().where(Node.validated == False)
    for node in nodes:
        now = datetime.utcnow()
        logging.info(f"Attempting to validate {node.url}")
        try:
            r = make_request(node.url)
            assert "height" in r.json()
            assert "nettype" in r.json()
            has_cors = "Access-Control-Allow-Origin" in r.headers
            is_ssl = node.url.startswith("https://")
            nettype = r.json()["nettype"]
            crypto = determine_crypto(node.url)
            if nettype in ["mainnet", "stagenet", "testnet"]:
                node.nettype = nettype
                node.available = True
                node.validated = True
                node.web_compatible = has_cors and is_ssl
                node.last_height = r.json()["height"]
                node.datetime_checked = now
                node.crypto = crypto
                node.is_tor = is_onion(node.url)
                node.is_i2p = is_i2p(node.url)
                if not node.is_tor and not node.is_i2p:
                    geoip = get_geoip(node.url)
                    node.country_name = geoip.country.name
                    node.country_code = geoip.country.iso_code
                    node.city = geoip.city.name
                    node.postal = geoip.postal.code
                    node.lat = geoip.location.latitude
                    node.lon = geoip.location.longitude
                    logging.info(f"found geo data for {node.url} - {node.country_code}, {node.country_name}, {node.city}")
                node.save()
                logging.info("success")
            else:
                logging.info("unexpected nettype")
        except requests.exceptions.ConnectTimeout:
            logging.info("connection timed out")
            node.delete_instance()
        except requests.exceptions.SSLError:
            logging.info("invalid certificate")
            node.delete_instance()
        except requests.exceptions.ConnectionError:
            logging.info("connection error")
            node.delete_instance()
        except requests.exceptions.HTTPError:
            logging.info("http error, 4xx or 5xx")
            node.delete_instance()
        except Exception as e:
            logging.info(f"failed for reasons unknown: {e}")
            node.delete_instance()


@bp.cli.command("export")
def export():
    all_nodes = []
    ts = int(arrow.get().timestamp())
    export_dir = f"{config.DATA_DIR}/export.txt"
    export_dir_stamped = f"{config.DATA_DIR}/export-{ts}.txt"
    nodes = Node.select().where(Node.validated == True)
    for node in nodes:
        logging.info(f"Adding {node.url}")
        all_nodes.append(node.url)
    with open(export_dir, "w") as f:
        f.write("\n".join(all_nodes))
    with open(export_dir_stamped, "w") as f:
        f.write("\n".join(all_nodes))
    logging.info(
        f"{nodes.count()} nodes written to {export_dir} and {export_dir_stamped}"
    )


@bp.cli.command("import")
def import_():
    all_nodes = []
    export_dir = f"{config.DATA_DIR}/export.txt"
    with open(export_dir, "r") as f:
        for url in f.readlines():
            try:
                n = url.rstrip().lower()
                logging.info(f"Adding {n}")
                node = Node(url=n)
                node.save()
                all_nodes.append(n)
            except:
                pass
    logging.info(f"{len(all_nodes)} node urls imported and ready to be validated")
