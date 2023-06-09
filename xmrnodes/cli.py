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


@bp.cli.command("get_peers")
def get_peers():
    """
    This command requests peers from the configured upstream node and fans out 
    to recursively scrape all other peers on the network. This will take
    several hours to run.
    """
    # keep track of all peers
    all_peers = []
    print("[+] Preparing to crawl Monero p2p network")
    print(f"[.] Retrieving initial peers from {config.NODE_HOST}:{config.NODE_PORT}")

    # start initial list of peers to scan
    peers_to_scan = retrieve_peers(config.NODE_HOST, config.NODE_PORT)
    print(f"[+] Found {len(peers_to_scan)} initial peers to begin scraping.")
    sleep(3)

    # helper function to add a new peer to the db or update an existing one
    def save_peer(peer):
        with geoip2.database.Reader("./data/GeoLite2-City.mmdb") as reader:
            _url = urlparse(peer)
            url = f"{_url.scheme}://{_url.netloc}".lower()
            # add new peer if not in db
            if not Peer.select().where(Peer.url == peer).exists():
                response = reader.city(_url.hostname)
                p = Peer(
                    url=peer,
                    country=response.country.name,
                    city=response.city.name,
                    postal=response.postal.code,
                    lat=response.location.latitude,
                    lon=response.location.longitude,
                )
                p.save()
                print(f"{peer} - saving new peer")
            # or update if it does
            else:
                p = Peer.select().where(Peer.url == peer).first()
                p.datetime = datetime.now()
                p.save()
            return _url
    
    # iterate over the whole list until all peers have been scanned
    # add new peers to the list
    # skip the peer if we've seen it already
    try:
        while peers_to_scan:
            _peer = peers_to_scan[0]
            peers_to_scan.pop(0)
            if _peer in all_peers:
                print(f'already found {_peer}')
                continue
            all_peers.append(_peer)
            try:
                peer = save_peer(_peer)
                peers_to_scan += retrieve_peers(peer.hostname, peer.port)
            except:
                pass
    except KeyboardInterrupt:
        print('Stopped.')

    print(
        f"[+] Found {len(all_peers)} peers from {config.NODE_HOST}:{config.NODE_PORT}"
    )
    print("[+] Deleting old Monero p2p peers")
    for p in Peer.select():
        if p.hours_elapsed() > config.PEER_LIFETIME:
            print(f"[.] Deleting {p.url}")
            p.delete_instance()
    rw_cache("map_peers", list(Peer.select().execute()))


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
