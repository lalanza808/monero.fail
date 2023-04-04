import logging
from datetime import datetime, timedelta

import geoip2.database
import arrow
import requests
from flask import Blueprint
from urllib.parse import urlparse

from xmrnodes.helpers import determine_crypto, is_onion, make_request
from xmrnodes.helpers import retrieve_peers, rw_cache, get_highest_block
from xmrnodes.models import Node, HealthCheck, Peer
from xmrnodes import config

bp = Blueprint("cli", "cli", cli_group=None)


@bp.cli.command("init")
def init():
    pass


@bp.cli.command("check")
def check():
    diff = datetime.utcnow() - timedelta(hours=24)
    checks = HealthCheck.select().where(HealthCheck.datetime <= diff)
    for check in checks:
        print("Deleting check", check.id)
        check.delete_instance()
    nodes = Node.select().where(Node.validated == True)
    for node in nodes:
        now = datetime.utcnow()
        hc = HealthCheck(node=node)
        logging.info(f"Attempting to check {node.url}")
        try:
            r = make_request(node.url)
            assert "status" in r.json()
            assert "offline" in r.json()
            assert "height" in r.json()
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
    all_peers = []
    print("[+] Preparing to crawl Monero p2p network")
    print(f"[.] Retrieving initial peers from {config.NODE_HOST}:{config.NODE_PORT}")
    initial_peers = retrieve_peers(config.NODE_HOST, config.NODE_PORT)
    with geoip2.database.Reader("./data/GeoLite2-City.mmdb") as reader:
        for peer in initial_peers:
            if peer not in all_peers:
                all_peers.append(peer)
            _url = urlparse(peer)
            url = f"{_url.scheme}://{_url.netloc}".lower()
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
            else:
                p = Peer.select().where(Peer.url == peer).first()
                p.datetime = datetime.now()
                p.save()

            try:
                print(f"[.] Retrieving crawled peers from {_url.netloc}")
                new_peers = retrieve_peers(_url.hostname, _url.port)
                for peer in new_peers:
                    if peer not in all_peers:
                        all_peers.append(peer)
                    _url = urlparse(peer)
                    url = f"{_url.scheme}://{_url.netloc}".lower()
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
                    else:
                        p = Peer.select().where(Peer.url == peer).first()
                        p.datetime = datetime.now()
                        p.save()
            except:
                pass

    print(
        f"[+] Found {len(all_peers)} peers from {config.NODE_HOST}:{config.NODE_PORT}"
    )
    print("[+] Deleting old Monero p2p peers")
    for p in Peer.select():
        if p.hours_elapsed() > 24:
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
            logging.info("success")
            if nettype in ["mainnet", "stagenet", "testnet"]:
                node.nettype = nettype
                node.available = True
                node.validated = True
                node.web_compatible = has_cors and is_ssl
                node.last_height = r.json()["height"]
                node.datetime_checked = now
                node.crypto = crypto
                node.is_tor = is_onion(node.url)
                node.save()
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
            logging.info("failed for reasons unknown")
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
