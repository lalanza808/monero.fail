import logging
from pathlib import Path
from datetime import datetime, timedelta
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed

import geoip2.database
import arrow
import requests
from peewee import BooleanField, CharField
from flask import Blueprint
from jinja2 import Environment, FileSystemLoader
from urllib.parse import urlparse

from xmrnodes.helpers import determine_crypto, is_onion, is_i2p, has_ipv6, make_request
from xmrnodes.helpers import retrieve_peers, get_highest_block, get_geoip, get_nodes
from xmrnodes.helpers import refresh_country_cache, make_lws_request
from xmrnodes.models import Node, HealthCheck, Peer, LWS, LWSHealthCheck
from xmrnodes import config

bp = Blueprint("cli", "cli", cli_group=None)


@bp.cli.command("rescan")
def rescan():
    for node in Node.select().where(Node.is_tor == False, Node.is_i2p == False):
        try:
            geodata = get_geoip(node.url)
            city = geodata.city.name
            state = geodata.subdivisions.most_specific.name
            country_code = geodata.country.iso_code
            country_name = geodata.country.name
            lat = geodata.location.latitude
            lon = geodata.location.longitude

            if city != node.city:
                print(f"changing {node.url} city: {node.city} -> {city}")
                node.city = city
            if state != node.state:
                print(f"changing {node.url} state: {node.state} -> {state}")
                node.state = state
            if country_code != node.country_code:
                print(f"changing {node.url} country_code: {node.country_code} -> {country_code}")
                node.country_code = country_code
            if country_name != node.country_name:
                print(f"changing {node.url} country_name: {node.country_name} -> {country_name}")
                node.country_name = country_name
            if lat != node.lat:
                print(f"changing {node.url} lat: {node.lat} -> {lat}")
                node.lat = lat
            if lon != node.lon:
                print(f"changing {node.url} lon: {node.lon} -> {lon}")
                node.lon = lon
            node.save()
        except Exception as e:
            print(f"Failed to update {node.url}: {e}")

@bp.cli.command("migrate")
def migrate():
    from playhouse.migrate import SqliteMigrator, migrate
    from xmrnodes.models import db
    migrator = SqliteMigrator(db)

    columns = [col.name for col in db.get_columns("peer")]
    if "country_code" not in columns:
        migrate(
            migrator.add_column("peer", "country_code", CharField(null=True)),
        )
        logging.info("Added country_code column to peer table")
    else:
        logging.info("country_code column already exists in peer table")

    # Backfill country_code for existing peers using GeoIP
    peers = Peer.select().where(Peer.country_code.is_null())
    for peer in peers:
        try:
            geodata = get_geoip(peer.url)
            peer.country_code = geodata.country.iso_code
            peer.save()
            print(f"Updated country_code for {peer.url}: {peer.country_code}")
        except Exception as e:
            print(f"Failed to update {peer.url}: {e}")

    # Ensure LWS and LWSHealthCheck tables exist
    tables = db.get_tables()
    if "lws" not in tables or "lwshealthcheck" not in tables:
        db.create_tables([LWS, LWSHealthCheck])
        logging.info("Created LWS and LWSHealthCheck tables")
    else:
        logging.info("LWS tables already exist")


@bp.cli.command("html")
def html():
    cur_dir = Path(__file__)
    env = Environment(loader=FileSystemLoader(Path(cur_dir.parent, "templates")))
    template = env.get_template('offline.html')
    rendered_html = template.render(get_nodes=get_nodes)
    offline_html_path = Path(config.DATA_DIR, 'offline.html')
    with open(offline_html_path, "w") as f:
        f.write(rendered_html)

@bp.cli.command("check")
def check_nodes():
    nodes = Node.select().where(
        Node.validated == True
    ).order_by(
        Node.datetime_checked.asc()
    ).limit(20)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_node, node.url): node for node in nodes}
        for future in as_completed(futures):
            try:
                future.result()
            except KeyboardInterrupt:
                exit()
            except Exception as e:
                logging.error(f"Error checking {futures[future].url}: {e}")
    refresh_country_cache()

def check_node(_node):
    if _node.startswith("http"):
        node = Node.select().where(Node.url == _node).first()
    else:
        node = Node.select().where(Node.id == _node).first()
    if not node:
        logging.info(f'{_node} not found')
        pass
    url = node.url
    now = datetime.utcnow()
    hc = HealthCheck(node=node, health=False)
    try:
        r = make_request(url)
        assert "status" in r.json()
        assert "offline" in r.json()
        assert "height" in r.json()
        if "donation_address" in r.json():
            node.donation_address = r.json()["donation_address"]
        has_cors = "Access-Control-Allow-Origin" in r.headers
        is_ssl = url.startswith("https://")
        if r.json()["status"] == "OK":
            node.web_compatible = has_cors and is_ssl
            node.last_height = r.json()["height"]
            hc.health = True
            highest_block = get_highest_block(node.nettype, node.crypto)
            healthy_block = highest_block - config.HEALTHY_BLOCK_DIFF
            if r.json()["height"] < healthy_block:
                node.available = False
                logging.info(f"{url} - unhealthy (behind {highest_block - r.json()['height']} blocks)")
            else:
                node.available = True
                logging.info(f"{url} - ok")
        else:
            raise
    except Exception as e:
        logging.info(f"{url} - failed ({e.__class__.__name__})")
        node.datetime_checked = now
        node.datetime_failed = now
        node.available = False
        hc.health = False
    node.datetime_checked = now
    node.is_ipv6 = has_ipv6(url)
    node.save()
    hc.save()
    failed_checks = node.get_failed_checks().count()
    all_checks = node.get_all_checks().count()
    if failed_checks == all_checks and all_checks > 15:
        logging.info(f"{url} - deleting (failed all {all_checks} checks)")
        for _hc in node.get_all_checks():
            _hc.delete_instance()
        node.delete_instance()
    else:
        # delete old healthchecks (only successful ones to preserve failure history)
        diff = now - timedelta(hours=240)
        hcs = 0
        for hc in node.healthchecks:
            if hc.datetime <= diff and hc.health == True:
                hcs += 1
                hc.delete_instance()
        if hcs:
            logging.info(f"{url} - pruned {hcs} old healthchecks")

def upsert_peer(peer):
    exists = Peer.select().where(Peer.url == peer).first()
    if exists:
        exists.datetime = datetime.utcnow()
        exists.save()
    else:
        try:
            geodata = get_geoip(url)
            p = Peer(
                url=_url,
                country=geodata.country.name,
                country_code=geodata.country.iso_code,
                city=geodata.city.name,
                state=geodata.subdivisions.most_specific.name,
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
        if not peers_to_scan:
            print("Could not find any peers. Sum ting wong.")
            return False
        print(f"[+] Found {len(peers_to_scan)} initial peers to begin scraping.")
        for peer in peers_to_scan:
            upsert_peer(peer)

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
    nodes = Node.select().where(Node.validated == False).limit(50)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(validate_node, node): node for node in nodes}
        for future in as_completed(futures):
            try:
                future.result()
            except KeyboardInterrupt:
                exit()
            except Exception as e:
                logging.error(f"{futures[future].url} - unexpected error: {e}")
    refresh_country_cache()

def validate_node(node):
    url = node.url
    now = datetime.utcnow()
    try:
        r = make_request(url)
        assert "height" in r.json()
        assert "nettype" in r.json()
        has_cors = "Access-Control-Allow-Origin" in r.headers
        is_ssl = url.startswith("https://")
        nettype = r.json()["nettype"]
        crypto = determine_crypto(url)
        if nettype in ["mainnet", "stagenet", "testnet"]:
            node.nettype = nettype
            node.available = True
            node.validated = True
            node.web_compatible = has_cors and is_ssl
            node.last_height = r.json()["height"]
            node.datetime_checked = now
            node.crypto = crypto
            node.is_tor = is_onion(url)
            node.is_i2p = is_i2p(url)
            node.is_ipv6 = has_ipv6(url)
            if not node.is_tor and not node.is_i2p:
                geoip = get_geoip(url)
                node.country_name = geoip.country.name
                node.country_code = geoip.country.iso_code
                node.city = geoip.city.name
                node.state = geoip.subdivisions.most_specific.name
                node.postal = geoip.postal.code
                node.lat = geoip.location.latitude
                node.lon = geoip.location.longitude
                ipv6_tag = ", IPv6" if node.is_ipv6 else ""
                logging.info(f"{url} - validated ({node.country_code}, {node.city}{ipv6_tag})")
            else:
                logging.info(f"{url} - validated")
            node.save()
        else:
            logging.info(f"{url} - unexpected nettype: {nettype}")
    except requests.exceptions.ConnectTimeout:
        logging.info(f"{url} - connection timed out, deleting")
        node.delete_instance()
    except requests.exceptions.SSLError:
        logging.info(f"{url} - invalid certificate, deleting")
        node.delete_instance()
    except requests.exceptions.ConnectionError:
        logging.info(f"{url} - connection error, deleting")
        node.delete_instance()
    except requests.exceptions.HTTPError:
        logging.info(f"{url} - http error, deleting")
        node.delete_instance()
    except Exception as e:
        logging.info(f"{url} - failed ({e}), deleting")
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


@bp.cli.command("validate_lws")
def validate_lws():
    """Validate unvalidated LWS servers by calling /get_version."""
    servers = LWS.select().where(LWS.validated == False).limit(50)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_validate_lws, server): server for server in servers}
        for future in as_completed(futures):
            try:
                future.result()
            except KeyboardInterrupt:
                exit()
            except Exception as e:
                logging.error(f"{futures[future].url} - unexpected error: {e}")


def _validate_lws(server):
    url = server.url
    now = datetime.utcnow()
    try:
        r = make_lws_request(url)
        data = r.json()
        # Must have at least network_type to be considered valid
        assert "network_type" in data, "missing network_type"

        server.server_type = data.get("server_type")
        server.server_version = data.get("server_version")
        server.last_git_commit_hash = data.get("last_git_commit_hash")
        server.last_git_commit_date = data.get("last_git_commit_date")
        server.git_branch_name = data.get("git_branch_name")
        server.monero_version_full = data.get("monero_version_full")
        server.blockchain_height = data.get("blockchain_height")
        server.api_version = data.get("api")
        server.max_subaddresses = data.get("max_subaddresses")
        server.network_type = data.get("network_type")
        server.available = True
        server.validated = True
        server.datetime_checked = now
        server.is_tor = is_onion(url)
        server.is_i2p = is_i2p(url)
        if not server.is_tor and not server.is_i2p:
            try:
                geoip = get_geoip(url)
                server.country_name = geoip.country.name
                server.country_code = geoip.country.iso_code
                server.city = geoip.city.name
                server.state = geoip.subdivisions.most_specific.name
                server.postal = geoip.postal.code
                server.lat = geoip.location.latitude
                server.lon = geoip.location.longitude
            except Exception:
                pass
            logging.info(f"{url} - validated ({server.network_type}, {server.server_type} {server.server_version})")
        else:
            logging.info(f"{url} - validated ({server.server_type} {server.server_version})")
        server.save()
    except requests.exceptions.ConnectTimeout:
        logging.info(f"{url} - connection timed out, deleting")
        server.delete_instance()
    except requests.exceptions.SSLError:
        logging.info(f"{url} - invalid certificate, deleting")
        server.delete_instance()
    except requests.exceptions.ConnectionError:
        logging.info(f"{url} - connection error, deleting")
        server.delete_instance()
    except requests.exceptions.HTTPError:
        logging.info(f"{url} - http error, deleting")
        server.delete_instance()
    except Exception as e:
        logging.info(f"{url} - failed ({e}), deleting")
        server.delete_instance()


@bp.cli.command("check_lws")
def check_lws():
    """Health-check validated LWS servers by calling /get_version."""
    servers = LWS.select().where(
        LWS.validated == True
    ).order_by(
        LWS.datetime_checked.asc()
    ).limit(20)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_check_lws, server.url): server for server in servers}
        for future in as_completed(futures):
            try:
                future.result()
            except KeyboardInterrupt:
                exit()
            except Exception as e:
                logging.error(f"Error checking LWS {futures[future].url}: {e}")


def _check_lws(_server):
    if _server.startswith("http"):
        server = LWS.select().where(LWS.url == _server).first()
    else:
        server = LWS.select().where(LWS.id == _server).first()
    if not server:
        logging.info(f'{_server} not found')
        return
    url = server.url
    now = datetime.utcnow()
    hc = LWSHealthCheck(lws=server, health=False)
    try:
        r = make_lws_request(url)
        data = r.json()
        assert "network_type" in data, "missing network_type"

        # Update server details from response
        server.server_type = data.get("server_type", server.server_type)
        server.server_version = data.get("server_version", server.server_version)
        server.last_git_commit_hash = data.get("last_git_commit_hash", server.last_git_commit_hash)
        server.last_git_commit_date = data.get("last_git_commit_date", server.last_git_commit_date)
        server.git_branch_name = data.get("git_branch_name", server.git_branch_name)
        server.monero_version_full = data.get("monero_version_full", server.monero_version_full)
        server.blockchain_height = data.get("blockchain_height", server.blockchain_height)
        server.api_version = data.get("api", server.api_version)
        server.max_subaddresses = data.get("max_subaddresses", server.max_subaddresses)
        server.network_type = data.get("network_type", server.network_type)
        server.available = True
        hc.health = True
        logging.info(f"{url} - ok (height: {server.blockchain_height})")
    except Exception as e:
        logging.info(f"{url} - failed ({e.__class__.__name__})")
        server.datetime_failed = now
        server.available = False
        server.fail_reason = str(e)[:255]
        hc.health = False
    server.datetime_checked = now
    server.save()
    hc.save()
    # Auto-delete persistently failing servers
    failed_checks = server.get_failed_checks().count()
    all_checks = server.get_all_checks().count()
    if failed_checks == all_checks and all_checks > 15:
        logging.info(f"{url} - deleting (failed all {all_checks} checks)")
        for _hc in server.get_all_checks():
            _hc.delete_instance()
        server.delete_instance()
    else:
        # Prune old successful healthchecks
        diff = now - timedelta(hours=240)
        hcs = 0
        for hc in server.healthchecks:
            if hc.datetime <= diff and hc.health == True:
                hcs += 1
                hc.delete_instance()
        if hcs:
            logging.info(f"{url} - pruned {hcs} old healthchecks")
