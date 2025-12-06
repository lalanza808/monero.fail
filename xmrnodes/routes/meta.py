import re
from random import shuffle, seed
from math import ceil
from datetime import timedelta

import arrow
from flask import request, redirect, Blueprint
from flask import render_template, flash, Response
from urllib.parse import urlparse

from xmrnodes.helpers import get_highest_block
from xmrnodes.forms import SubmitNode
from xmrnodes.models import Node, Peer
from xmrnodes import config

bp = Blueprint("meta", "meta")


@bp.route("/", methods=["GET", "POST"])
def index():
    form = SubmitNode()

    # Clean up query parameters

    # Extract parameters with defaults
    nettype = request.args.get("network", "mainnet")
    crypto = request.args.get("chain", "monero")
    node_type = request.args.get("type", "all")
    web_compatible = False

    # Validate and limit page number
    per_page = 100  # Number of nodes per page
    highest_block = get_highest_block(nettype, crypto)
    healthy_block = highest_block - config.HEALTHY_BLOCK_DIFF

    # Base query for nodes
    nodes = Node.select().where(
        Node.nettype == nettype,
        Node.crypto == crypto,
        Node.validated == True
    )

    if node_type == "clear":
        nodes = nodes.where(
            Node.web_compatible == False,
            Node.is_tor == False,
            Node.is_i2p == False
        )
    elif node_type == "onion":
        nodes = nodes.where(Node.is_tor == True)
    elif node_type == "i2p":
        nodes = nodes.where(Node.is_i2p == True)
    elif node_type == "cors":
        nodes = nodes.where(Node.web_compatible == True)
        web_compatible = True
    else:
        nodes = nodes.where(Node.is_i2p == False, Node.is_tor == False)

    nodes_all = nodes.count()
    nodes_unhealthy = nodes.where(
        (Node.available == False) | (Node.last_height < healthy_block)
    ).count()

    nodes = nodes.where(
        Node.available == True,
        Node.last_height > healthy_block
    ).order_by(Node.datetime_entered.desc())


    nodes_healthy = nodes.count()

    # Pagination
    total_pages = (nodes_healthy // per_page) + 1

    # Ensure page is within valid range
    page = request.args.get("page", "1")
    if not page.isdigit():
        return redirect("/")
    else:
        page = int(page)
    if page > total_pages:
        page = total_pages
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    if nodes_healthy < per_page:
        end_index = nodes_healthy
    seed(page)
    nodes_list = list(nodes)
    shuffle(nodes_list)
    paginated_nodes = nodes_list[start_index:end_index]
    next_page = None
    if page < total_pages:
        next_page = page + 1
    previous_page = None
    if page > 1:
        previous_page = page - 1

    return render_template(
        "index.html",
        nodes=paginated_nodes,
        nodes_all=nodes_all,
        nodes_unhealthy=nodes_unhealthy,
        nodes_healthy=nodes_healthy,
        nettype=nettype,
        crypto=crypto,
        form=form,
        web_compatible=web_compatible,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        next_page=next_page,
        previous_page=previous_page,
        start_index=start_index,
        end_index=end_index,
    )


@bp.route("/map")
def map():
    fetch = request.args.get("fetch")
    now = arrow.now()
    all_peers = Peer.select()
    peers = all_peers.order_by(Peer.datetime.desc()).limit(5000)
    if fetch:
        _peers = {}
        next = None
        limit = 1000
        rgb = "238,111,45"
        offset = request.args.get("offset", 0)
        offset = int(offset)
        
        paginated_peers = peers.paginate(offset, limit)
        total = ceil(peers.count() / limit)
        if offset < total:
            next = offset + 1
        for peer in paginated_peers:
            opacity = ".8"
            _peers[peer.url] = {
                "rgba": f"rgba({rgb},{opacity})",
                "lat": peer.lat,
                "lon": peer.lon,
                "last_seen": arrow.get(peer.datetime).humanize(granularity="hour")
            }
        return {
            "offset": offset,
            "next": next,
            "total": total,
            "peers": _peers
        }
    return render_template(
        "map.html",
        recent_peers=all_peers.count(),
        source_node=config.NODE_HOST,
        shown_peers=peers.count()
    )


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/opsec")
def opsec():
    return render_template("opsec.html")


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        url = request.form.get("node_url", "").strip()
        if not url:
            flash("URL is required")
            return redirect("/")

        regex = re.compile(
            r"^(?:http)s?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        if not regex.match(url):
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
