import arrow
import json
import requests
import re
import logging
from os import makedirs
from datetime import datetime
from flask import Flask, request, redirect
from flask import render_template, flash, url_for
from urllib.parse import urlparse
from xmrnodes.helpers import determine_crypto
from xmrnodes.forms import SubmitNode
from xmrnodes.models import Node
from xmrnodes import config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)
app.config.from_envvar("FLASK_SECRETS")
app.secret_key = app.config["SECRET_KEY"]

@app.route("/", methods=["GET", "POST"])
def index():
    form = SubmitNode()
    itp = 20
    page = request.args.get("page", 1)
    try:
        page = int(page)
    except:
        flash("Wow, wtf hackerman. Cool it.")
        page = 1

    nettype = request.args.get("nettype", "mainnet")
    crypto = request.args.get("crypto", "monero")

    nodes = Node.select().where(
        Node.validated==True
    ).where(
        Node.nettype==nettype
    ).where(
        Node.crypto==crypto
    ).order_by(
        Node.datetime_entered.desc()
    )
    paginated = nodes.paginate(page, itp)
    total_pages = nodes.count() / itp
    return render_template(
        "index.html",
        nodes=paginated,
        page=page,
        total_pages=total_pages,
        form=form
    )


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
            url = f"{_url.scheme}://{_url.netloc}"
            if Node.select().where(Node.url == url).exists():
                flash("This node is already in the database.")
            else:
                flash("Seems like a valid node URL. Added to the database and will check soon.")
                node = Node(url=url)
                node.save()
    return redirect("/")

@app.cli.command("check")
def check():
    nodes = Node.select().where(Node.validated == True)
    for node in nodes:
        now = datetime.utcnow()
        logging.info(f"Attempting to check {node.url}")
        try:
            r = requests.get(node.url + "/get_info", timeout=5)
            r.raise_for_status()
            assert "status" in r.json()
            assert "offline" in r.json()
            assert "height" in r.json()
            if r.json()["status"] == "OK":
                logging.info("success")
                node.available = True
                node.last_height = r.json()["height"]
            else:
                raise
        except:
            logging.info("fail")
            node.datetime_failed = now
            node.available = False
        finally:
            node.datetime_checked = now
            node.save()

@app.cli.command("validate")
def validate():
    nodes = Node.select().where(Node.validated == False)
    for node in nodes:
        now = datetime.utcnow()
        is_onion = node.url.split(":")[1].endswith(".onion")
        logging.info(f"Attempting to validate {node.url}")
        if is_onion:
            logging.info("onion address found")
            node.is_tor = True
        try:
            r = requests.get(node.url + "/get_info", timeout=5)
            r.raise_for_status()
            assert "height" in r.json()
            assert "nettype" in r.json()
            nettype = r.json()["nettype"]
            crypto = determine_crypto(node.url)
            logging.info("success")
            if nettype in ["mainnet", "stagenet", "testnet"]:
                node.nettype = nettype
                node.available = True
                node.validated = True
                node.last_height = r.json()["height"]
                node.datetime_checked = now
                node.crypto = crypto
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
    export_dir = f"{config.DATA_DIR}/export.txt"
    nodes = Node.select().where(Node.validated == True)
    for node in nodes:
        all_nodes.append(node.url)
    with open(export_dir, "w") as f:
        f.write("\n".join(all_nodes))
    logging.info(f"{nodes.count()} nodes written to {export_dir}")

@app.template_filter("humanize")
def humanize(d):
    t = arrow.get(d, "UTC")
    return t.humanize()

if __name__ == "__main__":
    app.run()
