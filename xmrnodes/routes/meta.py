import re
from random import shuffle

from flask import request, redirect, Blueprint
from flask import render_template, flash, Response
from urllib.parse import urlparse

from xmrnodes.helpers import rw_cache, get_highest_block
from xmrnodes.forms import SubmitNode
from xmrnodes.models import Node
from xmrnodes import config

bp = Blueprint("meta", "meta")


@bp.route("/", methods=["GET", "POST"])
def index():
    form = SubmitNode()
    nettype = request.args.get("network", "mainnet")
    crypto = request.args.get("chain", "monero")
    onion = request.args.get("onion", False)
    i2p = request.args.get("i2p", False)
    show_all = "true" == request.args.get("all", "false")
    web_compatible = request.args.get("cors", False)
    highest_block = get_highest_block(nettype, crypto)
    healthy_block = highest_block - config.HEALTHY_BLOCK_DIFF

    nodes = Node.select().where(
        Node.validated == True, Node.nettype == nettype, Node.crypto == crypto
    )

    if web_compatible:
        nodes = nodes.where(Node.web_compatible == True)

    nodes_all = nodes.count()
    nodes_unhealthy = nodes.where(
        (Node.available == False) | (Node.last_height < healthy_block)
    ).count()

    if not show_all:
        nodes = nodes.where(Node.available == True, Node.last_height > healthy_block)

    nodes = nodes.order_by(Node.datetime_entered.desc())
    if onion:
        nodes = nodes.where(Node.is_tor == True)
    if i2p:
        nodes = nodes.where(Node.is_i2p == True)

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
        web_compatible=web_compatible,
    )


@bp.route("/map")
def map():
    try:
        peers = rw_cache("map_peers")
    except:
        flash("Couldn't load the map. Try again later.")
        return redirect("/")
    return render_template("map.html", peers=peers, source_node=config.NODE_HOST)


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        url = request.form.get("node_url")
        regex = re.compile(
            r"^(?:http)s?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        re_match = re.match(regex, url)
        if re_match is None:
            flash("This doesn't look like a valid URL")
        else:
            _url = urlparse(url)
            url = f"{_url.scheme}://{_url.netloc}".lower()
            if Node.select().where(Node.url == url).exists():
                flash("This node is already in the database.")
            else:
                flash(
                    "Seems like a valid node URL. Added to the database and will check soon."
                )
                node = Node(url=url)
                node.save()
    return redirect("/")


@bp.route("/haproxy.cfg")
def haproxy():
    crypto = request.args.get("chain") or "monero"
    nettype = request.args.get("network") or "mainnet"
    cors = request.args.get("cors") or False
    tor = request.args.get("onion") or False
    nodes = Node.select().where(
        Node.validated == True,
        Node.nettype == nettype,
        Node.crypto == crypto,
        Node.is_tor == tor,
        Node.web_compatible == cors,
    )
    tpl = render_template("haproxy.html", nodes=nodes)
    res = Response(tpl)
    res.headers[
        "Content-Disposition"
    ] = f'attachment; filename="haproxy-{crypto}-{nettype}-cors_{cors}-tor_{tor}.cfg"'
    return res
