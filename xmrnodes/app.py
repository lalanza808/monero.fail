import re
import logging
from random import shuffle
from datetime import datetime, timedelta

import geoip2.database
import arrow
import requests
from flask import Flask, request, redirect, jsonify
from flask import render_template, flash, Response
from urllib.parse import urlparse, urlencode

from xmrnodes.helpers import determine_crypto, is_onion, make_request
from xmrnodes.helpers import retrieve_peers, rw_cache, get_highest_block
from xmrnodes.forms import SubmitNode
from xmrnodes.models import Node, HealthCheck, Peer
from xmrnodes import config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)
app.config.from_envvar("FLASK_SECRETS")
app.secret_key = app.config["SECRET_KEY"]
HEALTHY_BLOCK_DIFF = 500 # idc to config this. hardcode is fine.

@app.route("/", methods=["GET", "POST"])
def index():
    form = SubmitNode()
    nettype = request.args.get("network", "mainnet")
    crypto = request.args.get("chain", "monero")
    onion = request.args.get("onion", False)
    show_all = "true" == request.args.get("all", "false")
    web_compatible = request.args.get("cors", False)
    highest_block = get_highest_block(nettype, crypto)
    healthy_block = highest_block - HEALTHY_BLOCK_DIFF

    nodes = Node.select().where(
        Node.validated == True,
        Node.nettype == nettype,
        Node.crypto == crypto
    )

    if web_compatible:
        nodes = nodes.where(Node.web_compatible == True)

    nodes_all = nodes.count()
    nodes_unhealthy = nodes.where(
        (Node.available == False) | (Node.last_height < healthy_block)
    ).count()

    if not show_all:
        nodes = nodes.where(
            Node.available == True,
            Node.last_height > healthy_block
        )

    nodes = nodes.order_by(
        Node.datetime_entered.desc()
    )
    if onion:
        nodes = nodes.where(Node.is_tor == True)

    nodes = [n for n in nodes]
    shuffle(nodes)

    return render_template(
        "index.html",
        nodes=nodes,
        nodes_all=nodes_all,
        nodes_unhealthy=nodes_unhealthy,
        nettype=nettype,
        crypto=crypto,
        form=form,
        web_compatible=web_compatible
    )

@app.route("/nodes.json")
def nodes_json():
    nodes = Node.select().where(
        Node.validated==True
    ).where(
        Node.nettype=="mainnet"
    )
    xmr_nodes = [n for n in nodes if n.crypto == "monero"]
    wow_nodes = [n for n in nodes if n.crypto == "wownero"]
    return jsonify({
        "monero": {
            "clear": [n.url for n in xmr_nodes if n.is_tor == False],
            "onion": [n.url for n in xmr_nodes if n.is_tor == True],
            "web_compatible": [n.url for n in xmr_nodes if n.web_compatible == True],
        },
        "wownero": {
            "clear": [n.url for n in wow_nodes if n.is_tor == False],
            "onion": [n.url for n in wow_nodes if n.is_tor == True]
        }
    })

@app.route("/haproxy.cfg")
def haproxy():
    crypto = request.args.get('chain') or 'monero'
    nettype = request.args.get('network') or 'mainnet'
    cors = request.args.get('cors') or False
    tor = request.args.get('onion') or False
    nodes = Node.select().where(
        Node.validated == True,
        Node.nettype == nettype,
        Node.crypto == crypto,
        Node.is_tor == tor,
        Node.web_compatible == cors
    )
    tpl = render_template("haproxy.html", nodes=nodes)
    print(tpl)
    res = Response(tpl)
    res.headers['Content-Disposition'] = f'attachment; filename="haproxy-{crypto}-{nettype}-cors_{cors}-tor_{tor}.cfg"'
    return res

@app.route("/wow_nodes.json")
def wow_nodes_json():
    nodes = Node.select().where(
        Node.validated==True
    ).where(
        Node.nettype=="mainnet"
    ).where(
        Node.crypto=="wownero"
    )
    nodes = [n for n in nodes]
    return jsonify({
        "clear": [n.url for n in nodes if n.is_tor == False],
        "onion": [n.url for n in nodes if n.is_tor == True]
    })

@app.route("/map")
def map():
    return render_template(
        "map.html",
        peers=rw_cache('map_peers'),
        source_node=config.NODE_HOST
    )

@app.route("/resources")
def resources():
    return render_template("resources.html")

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        url = request.form.get("node_url")
        regex = re.compile(
            r"^(?:http)s?://" # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|" #domain...
            r"localhost|" #localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})" # ...or ip
            r"(?::\d+)?" # optional port
            r"(?:/?|[/?]\S+)$", re.IGNORECASE
        )
        re_match = re.match(regex, url)
        if re_match is None:
            flash("This doesn\"t look like a valid URL")
        else:
            _url = urlparse(url)
            url = f"{_url.scheme}://{_url.netloc}".lower()
            if Node.select().where(Node.url == url).exists():
                flash("This node is already in the database.")
            else:
                flash("Seems like a valid node URL. Added to the database and will check soon.")
                node = Node(url=url)
                node.save()
    return redirect("/")

def cleanup_health_checks():
    diff = datetime.utcnow() - timedelta(hours=24)
    checks = HealthCheck.select().where(HealthCheck.datetime <= diff)
    for check in checks:
        print("Deleting check", check.id)
        check.delete_instance()

@app.cli.command("check")
def check():
    cleanup_health_checks()
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
            has_cors = 'Access-Control-Allow-Origin' in r.headers
            is_ssl = node.url.startswith('https://')
            if r.json()["status"] == "OK":
                node.web_compatible = has_cors and is_ssl
                node.last_height = r.json()["height"]
                hc.health = True
                highest_block = get_highest_block(node.nettype, node.crypto)
                healthy_block = highest_block - HEALTHY_BLOCK_DIFF
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
        if node.get_failed_checks().count() == node.get_all_checks().count() and node.get_all_checks().count() > 5:
            print('this node fails all of its health checks - deleting it!')
            for _hc in node.get_all_checks():
                _hc.delete_instance()
            node.delete_instance()

@app.cli.command("get_peers")
def get_peers():
    all_peers = []
    print('[+] Preparing to crawl Monero p2p network')
    print(f'[.] Retrieving initial peers from {config.NODE_HOST}:{config.NODE_PORT}')
    initial_peers = retrieve_peers(config.NODE_HOST, config.NODE_PORT)
    with geoip2.database.Reader('./data/GeoLite2-City.mmdb') as reader:
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
                print(f'{peer} - saving new peer')
            else:
                p = Peer.select().where(Peer.url == peer).first()
                p.datetime = datetime.now()
                p.save()

            try:
                print(f'[.] Retrieving crawled peers from {_url.netloc}')
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
                        print(f'{peer} - saving new peer')
                    else:
                        p = Peer.select().where(Peer.url == peer).first()
                        p.datetime = datetime.now()
                        p.save()
            except:
                pass

    print(f'[+] Found {len(all_peers)} peers from {config.NODE_HOST}:{config.NODE_PORT}')
    print('[+] Deleting old Monero p2p peers')
    for p in Peer.select():
        if p.hours_elapsed() > 24:
            print(f'[.] Deleting {p.url}')
            p.delete_instance()
    rw_cache('map_peers', list(Peer.select().execute()))


@app.cli.command("validate")
def validate():
    nodes = Node.select().where(Node.validated == False)
    for node in nodes:
        now = datetime.utcnow()
        logging.info(f"Attempting to validate {node.url}")
        try:
            r = make_request(node.url)
            assert "height" in r.json()
            assert "nettype" in r.json()
            has_cors = 'Access-Control-Allow-Origin' in r.headers
            is_ssl = node.url.startswith('https://')
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

@app.cli.command("export")
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
    logging.info(f"{nodes.count()} nodes written to {export_dir} and {export_dir_stamped}")

@app.cli.command("import")
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

@app.template_filter("humanize")
def humanize(d):
    t = arrow.get(d, "UTC")
    return t.humanize()

@app.template_filter("hours_elapsed")
def hours_elapsed(d):
    now = datetime.utcnow()
    diff = now - d
    return diff.total_seconds() / 60 / 60

@app.template_filter("pop_arg")
def trim_arg(all_args, arg_to_trim):
    d = all_args.to_dict()
    d.pop(arg_to_trim)
    return urlencode(d)

if __name__ == "__main__":
    app.run()
