from flask import jsonify, Blueprint
from flask_restx import Api, Resource, Namespace, fields, reqparse

from xmrnodes.helpers import get_highest_block, haversine
from xmrnodes.models import Node, HealthCheck, Peer
from xmrnodes import config


bp = Blueprint("api", "api")

# =============================================================================
# Legacy JSON endpoints (kept for backward compatibility)
# =============================================================================

@bp.route("/nodes.json")
def nodes_json():
    nodes = Node.select().where(
        Node.validated == True,
        Node.available == True,
        Node.nettype == "mainnet"
    )
    xmr_nodes = [n for n in nodes if n.crypto == "monero"]
    wow_nodes = [n for n in nodes if n.crypto == "wownero"]
    return jsonify({
        "monero": {
            "clear": [n.url for n in xmr_nodes if n.is_tor == False and n.is_i2p == False],
            "onion": [n.url for n in xmr_nodes if n.is_tor == True],
            "i2p": [n.url for n in xmr_nodes if n.is_i2p == True],
            "ipv6": [n.url for n in xmr_nodes if n.is_ipv6 == True],
            "web_compatible": [n.url for n in xmr_nodes if n.web_compatible == True],
        },
        "wownero": {
            "clear": [n.url for n in wow_nodes if n.is_tor == False and n.is_i2p == False],
            "onion": [n.url for n in wow_nodes if n.is_tor == True],
            "i2p": [n.url for n in wow_nodes if n.is_i2p == True],
            "ipv6": [n.url for n in wow_nodes if n.is_ipv6 == True],
            "web_compatible": [n.url for n in wow_nodes if n.web_compatible == True],
        }
    })

@bp.route("/health.json")
def health_json():
    data = {}
    nodes = Node.select().where(
        Node.validated == True
    )
    for node in nodes:
        if node.crypto not in data:
            data[node.crypto] = {}
        _d = {
            "available": node.available,
            "last_height": node.last_height,
            "datetime_entered": node.datetime_entered,
            "datetime_checked": node.datetime_checked,
            "datetime_failed": node.datetime_failed,
            "checks": [c.health for c in node.get_all_checks()]
        }
        nettype = "clear"
        if node.is_tor:
            nettype = "onion"
        elif node.web_compatible:
            if "web_compatible" not in data[node.crypto]:
                data[node.crypto]["web_compatible"] = {}
            data[node.crypto]["web_compatible"][node.url] = _d
        if nettype not in data[node.crypto]:
            data[node.crypto][nettype] = {}
        data[node.crypto][nettype][node.url] = _d
    return jsonify(data)

@bp.route("/wow_nodes.json")
def wow_nodes_json():
    nodes = Node.select().where(
        Node.validated == True
    ).where(
        Node.nettype == "mainnet"
    ).where(
        Node.crypto == "wownero"
    )
    nodes = [n for n in nodes]
    return jsonify({
        "clear": [n.url for n in nodes if n.is_tor == False],
        "onion": [n.url for n in nodes if n.is_tor == True]
    })


# =============================================================================
# REST API v1 with Swagger documentation
# =============================================================================


api = Api(
    bp,
    version="1.0",
    title="monero.fail API",
    description=(
        "Public REST API for querying Monero remote node status. "
        "Use this API to discover healthy remote nodes, filter by network type, "
        "geography, and connection type. No authentication required."
    ),
    doc="/api/v1/docs",
    prefix="/api/v1",
    authorizations=None
)

# --- Namespaces ---
ns_nodes = api.namespace(
    "nodes", description="Query and filter remote nodes"
)
ns_health = api.namespace(
    "health", description="Node health check data"
)
ns_peers = api.namespace(
    "peers", description="Discovered P2P peer information"
)

# --- Response models ---
node_model = api.model("Node", {
    "url": fields.String(description="Node URL (scheme://host:port)"),
    "available": fields.Boolean(description="Whether the node is currently reachable"),
    "web_compatible": fields.Boolean(description="Whether the node supports CORS for browser access"),
    "is_tor": fields.Boolean(description="Whether this is a Tor (.onion) node"),
    "is_i2p": fields.Boolean(description="Whether this is an I2P (.i2p) node"),
    "is_ipv6": fields.Boolean(description="Whether this is an IPv6 node"),
    "nettype": fields.String(description="Network type: mainnet, stagenet, or testnet"),
    "crypto": fields.String(description="Cryptocurrency: monero or wownero"),
    "last_height": fields.Integer(description="Last known block height"),
    "country_name": fields.String(description="Country where node is hosted"),
    "country_code": fields.String(description="ISO country code"),
    "city": fields.String(description="City where node is hosted"),
    "lat": fields.Float(description="Latitude"),
    "lon": fields.Float(description="Longitude"),
    "datetime_entered": fields.DateTime(description="When the node was added"),
    "datetime_checked": fields.DateTime(description="Last time the node was checked"),
    "datetime_failed": fields.DateTime(description="Last time the node failed a check"),
    "fail_reason": fields.String(description="Reason for last failure"),
})

nodes_response = api.model("NodesResponse", {
    "total": fields.Integer(description="Total number of matching nodes"),
    "page": fields.Integer(description="Current page number"),
    "per_page": fields.Integer(description="Results per page"),
    "pages": fields.Integer(description="Total number of pages"),
    "nodes": fields.List(fields.Nested(node_model)),
})

health_entry = api.model("HealthEntry", {
    "datetime": fields.DateTime(description="When the check occurred"),
    "health": fields.Boolean(description="Whether the node was healthy"),
})

node_health_model = api.model("NodeHealth", {
    "url": fields.String(description="Node URL"),
    "available": fields.Boolean(description="Current availability status"),
    "last_height": fields.Integer(description="Last known block height"),
    "checks": fields.List(fields.Nested(health_entry), description="Recent health checks"),
})

node_health_response = api.model("NodeHealthResponse", {
    "total": fields.Integer(description="Total number of matching nodes"),
    "page": fields.Integer(description="Current page number"),
    "per_page": fields.Integer(description="Results per page"),
    "pages": fields.Integer(description="Total number of pages"),
    "nodes": fields.List(fields.Nested(node_health_model)),
})

nearby_node_model = api.model("NearbyNode", {
    "url": fields.String(description="Node URL"),
    "distance_km": fields.Float(description="Distance from provided coordinates in km"),
    "country_name": fields.String(description="Country name"),
    "country_code": fields.String(description="ISO country code"),
    "city": fields.String(description="City name"),
    "lat": fields.Float(description="Node latitude"),
    "lon": fields.Float(description="Node longitude"),
    "last_height": fields.Integer(description="Last known block height"),
    "web_compatible": fields.Boolean(description="CORS support"),
    "is_ipv6": fields.Boolean(description="IPv6 node"),
})

nearby_response = api.model("NearbyResponse", {
    "total": fields.Integer(description="Total matching nodes"),
    "nodes": fields.List(fields.Nested(nearby_node_model)),
})

peer_model = api.model("Peer", {
    "url": fields.String(description="Peer URL (scheme://host:port)"),
    "hostname": fields.String(description="Peer hostname/IP"),
    "port": fields.Integer(description="Peer port number"),
    "country": fields.String(description="Country where peer is located"),
    "country_code": fields.String(description="ISO country code"),
    "city": fields.String(description="City where peer is located"),
    "state": fields.String(description="State/region where peer is located"),
    "postal": fields.String(description="Postal code"),
    "lat": fields.Float(description="Latitude"),
    "lon": fields.Float(description="Longitude"),
    "datetime": fields.DateTime(description="When the peer was discovered"),
})

peers_response = api.model("PeersResponse", {
    "total": fields.Integer(description="Total number of matching peers"),
    "page": fields.Integer(description="Current page number"),
    "per_page": fields.Integer(description="Results per page"),
    "pages": fields.Integer(description="Total number of pages"),
    "peers": fields.List(fields.Nested(peer_model)),
})

# --- Request parsers ---
nodes_parser = reqparse.RequestParser()
nodes_parser.add_argument(
    "crypto", type=str, default="monero",
    choices=("monero", "wownero"),
    help="Cryptocurrency network (monero or wownero)",
    location="args"
)
nodes_parser.add_argument(
    "network", type=str, default="mainnet",
    choices=("mainnet", "stagenet", "testnet"),
    help="Network type",
    location="args"
)
nodes_parser.add_argument(
    "type", type=str, default="all",
    choices=("all", "clear", "onion", "i2p", "ipv6", "cors"),
    help="Connection type filter",
    location="args"
)
nodes_parser.add_argument(
    "country", type=str, default=None,
    help="Filter by ISO country code (e.g. US, DE, FR)",
    location="args"
)
nodes_parser.add_argument(
    "healthy", type=str, default="true",
    choices=("true", "false", "all"),
    help="Filter by health status: true (healthy only), false (unhealthy only), all (no filter)",
    location="args"
)
nodes_parser.add_argument(
    "page", type=int, default=1,
    help="Page number (1-indexed)",
    location="args"
)
nodes_parser.add_argument(
    "per_page", type=int, default=50,
    help="Results per page (max 100)",
    location="args"
)

health_parser = reqparse.RequestParser()
health_parser.add_argument(
    "crypto", type=str, default="monero",
    choices=("monero", "wownero"),
    help="Cryptocurrency network",
    location="args"
)
health_parser.add_argument(
    "network", type=str, default="mainnet",
    choices=("mainnet", "stagenet", "testnet"),
    help="Network type",
    location="args"
)
health_parser.add_argument(
    "type", type=str, default="all",
    choices=("all", "clear", "onion", "i2p", "ipv6", "cors"),
    help="Connection type filter",
    location="args"
)
health_parser.add_argument(
    "page", type=int, default=1,
    help="Page number (1-indexed)",
    location="args"
)
health_parser.add_argument(
    "per_page", type=int, default=25,
    help="Results per page (max 50)",
    location="args"
)

nearby_parser = reqparse.RequestParser()
nearby_parser.add_argument(
    "lat", type=float, required=True,
    help="Latitude coordinate",
    location="args"
)
nearby_parser.add_argument(
    "lon", type=float, required=True,
    help="Longitude coordinate",
    location="args"
)
nearby_parser.add_argument(
    "crypto", type=str, default="monero",
    choices=("monero", "wownero"),
    help="Cryptocurrency network",
    location="args"
)
nearby_parser.add_argument(
    "network", type=str, default="mainnet",
    choices=("mainnet", "stagenet", "testnet"),
    help="Network type",
    location="args"
)
nearby_parser.add_argument(
    "limit", type=int, default=50,
    help="Maximum number of results (max 100)",
    location="args"
)

peers_parser = reqparse.RequestParser()
peers_parser.add_argument(
    "country", type=str, default=None,
    help="Filter by ISO country code (e.g. US, DE, FR)",
    location="args"
)
peers_parser.add_argument(
    "page", type=int, default=1,
    help="Page number (1-indexed)",
    location="args"
)
peers_parser.add_argument(
    "per_page", type=int, default=50,
    help="Results per page (max 100)",
    location="args"
)


# --- Helper functions ---
def serialize_node(node):
    """Convert a Node model instance to a dictionary."""
    return {
        "url": node.url,
        "available": node.available,
        "web_compatible": node.web_compatible,
        "is_tor": node.is_tor,
        "is_i2p": node.is_i2p,
        "is_ipv6": node.is_ipv6,
        "nettype": node.nettype,
        "crypto": node.crypto,
        "last_height": node.last_height,
        "country_name": node.country_name,
        "country_code": node.country_code,
        "city": node.city,
        "lat": node.lat,
        "lon": node.lon,
        "datetime_entered": node.datetime_entered.isoformat() if node.datetime_entered else None,
        "datetime_checked": node.datetime_checked.isoformat() if node.datetime_checked else None,
        "datetime_failed": node.datetime_failed.isoformat() if node.datetime_failed else None,
        "fail_reason": node.fail_reason,
    }


def serialize_peer(peer):
    """Convert a Peer model instance to a dictionary."""
    return {
        "url": peer.url,
        "hostname": peer.hostname,
        "port": peer.port,
        "country": peer.country,
        "country_code": peer.country_code,
        "city": peer.city,
        "state": peer.state,
        "postal": str(peer.postal) if peer.postal is not None else None,
        "lat": peer.lat,
        "lon": peer.lon,
        "datetime": peer.datetime.isoformat() if peer.datetime else None,
    }


def apply_type_filter(query, node_type):
    """Apply connection type filter to a query."""
    if node_type == "clear":
        query = query.where(Node.is_tor == False, Node.is_i2p == False)
    elif node_type == "onion":
        query = query.where(Node.is_tor == True)
    elif node_type == "i2p":
        query = query.where(Node.is_i2p == True)
    elif node_type == "ipv6":
        query = query.where(Node.is_ipv6 == True)
    elif node_type == "cors":
        query = query.where(Node.web_compatible == True)
    return query


# --- Endpoints ---
@ns_nodes.route("/")
class NodeList(Resource):
    @ns_nodes.doc("list_nodes")
    @ns_nodes.expect(nodes_parser)
    @ns_nodes.marshal_with(nodes_response)
    def get(self):
        """List and filter remote nodes.

        Returns a paginated list of validated remote nodes. Filter by cryptocurrency,
        network type, connection type, country, and health status.
        """
        args = nodes_parser.parse_args()
        crypto = args["crypto"]
        nettype = args["network"]
        node_type = args["type"]
        country = args["country"]
        healthy = args["healthy"]
        page = max(1, args["page"])
        per_page = min(100, max(1, args["per_page"]))

        # Base query
        query = Node.select().where(
            Node.validated == True,
            Node.nettype == nettype,
            Node.crypto == crypto,
        )

        # Connection type filter
        query = apply_type_filter(query, node_type)

        # Country filter
        if country:
            query = query.where(Node.country_code == country.upper())

        # Health filter
        if healthy != "all":
            highest_block = get_highest_block(nettype, crypto)
            healthy_block = highest_block - config.HEALTHY_BLOCK_DIFF
            if healthy == "true":
                query = query.where(
                    Node.available == True,
                    Node.last_height > healthy_block
                )
            else:
                query = query.where(
                    (Node.available == False) | (Node.last_height <= healthy_block)
                )

        query = query.order_by(Node.datetime_entered.desc())
        total = query.count()
        pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, pages)
        offset = (page - 1) * per_page
        nodes = query.offset(offset).limit(per_page)

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "nodes": [serialize_node(n) for n in nodes],
        }


@ns_nodes.route("/<string:node_url>")
@ns_nodes.param("node_url", "The node URL (URL-encoded, e.g. http%3A%2F%2Fhost%3Aport)")
class NodeDetail(Resource):
    @ns_nodes.doc("get_node")
    @ns_nodes.marshal_with(node_model)
    @ns_nodes.response(404, "Node not found")
    def get(self, node_url):
        """Get details for a specific node by URL."""
        from urllib.parse import unquote
        decoded_url = unquote(node_url)
        try:
            node = Node.get(Node.url == decoded_url, Node.validated == True)
        except Node.DoesNotExist:
            api.abort(404, f"Node not found: {decoded_url}")
        return serialize_node(node)


@ns_health.route("/")
class HealthList(Resource):
    @ns_health.doc("list_health")
    @ns_health.expect(health_parser)
    @ns_health.marshal_with(node_health_response)
    def get(self):
        """Get health check history for nodes.

        Returns paginated nodes with their recent health check history.
        Useful for monitoring node reliability over time.
        """
        args = health_parser.parse_args()
        crypto = args["crypto"]
        nettype = args["network"]
        node_type = args["type"]
        page = max(1, args["page"])
        per_page = min(50, max(1, args["per_page"]))

        query = Node.select().where(
            Node.validated == True,
            Node.nettype == nettype,
            Node.crypto == crypto,
        )

        query = apply_type_filter(query, node_type)
        query = query.order_by(Node.datetime_checked.desc())

        total = query.count()
        pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, pages)
        offset = (page - 1) * per_page
        nodes = query.offset(offset).limit(per_page)

        results = []
        for node in nodes:
            checks = (
                HealthCheck.select()
                .where(HealthCheck.node == node)
                .order_by(HealthCheck.datetime.desc())
                .limit(20)
            )
            results.append({
                "url": node.url,
                "available": node.available,
                "last_height": node.last_height,
                "checks": [
                    {
                        "datetime": c.datetime.isoformat() if c.datetime else None,
                        "health": c.health,
                    }
                    for c in checks
                ],
            })

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "nodes": results,
        }


@ns_nodes.route("/nearby")
class NearbyNodes(Resource):
    @ns_nodes.doc("find_nearby")
    @ns_nodes.expect(nearby_parser)
    @ns_nodes.marshal_with(nearby_response)
    def get(self):
        """Find nodes nearest to a geographic location.

        Provide latitude and longitude coordinates to get nodes sorted by
        proximity. Only returns healthy clearnet nodes with known locations.
        """
        args = nearby_parser.parse_args()
        lat = args["lat"]
        lon = args["lon"]
        crypto = args["crypto"]
        nettype = args["network"]
        limit = min(100, max(1, args["limit"]))

        highest_block = get_highest_block(nettype, crypto)
        healthy_block = highest_block - config.HEALTHY_BLOCK_DIFF

        nodes = Node.select().where(
            Node.validated == True,
            Node.available == True,
            Node.nettype == nettype,
            Node.crypto == crypto,
            Node.lat.is_null(False),
            Node.lon.is_null(False),
            Node.is_tor == False,
            Node.is_i2p == False,
            Node.last_height > healthy_block,
        )

        results = []
        for node in nodes:
            dist = haversine(lat, lon, node.lat, node.lon)
            results.append({
                "url": node.url,
                "distance_km": round(dist, 1),
                "country_name": node.country_name,
                "country_code": node.country_code,
                "city": node.city,
                "lat": node.lat,
                "lon": node.lon,
                "last_height": node.last_height,
                "web_compatible": node.web_compatible,
                "is_ipv6": node.is_ipv6,
            })

        results.sort(key=lambda x: x["distance_km"])
        return {"nodes": results[:limit], "total": len(results)}


@ns_peers.route("/")
class PeerList(Resource):
    @ns_peers.doc("list_peers")
    @ns_peers.expect(peers_parser)
    @ns_peers.marshal_with(peers_response)
    def get(self):
        """List discovered P2P peers.

        Returns a paginated list of peers discovered via the Levin P2P protocol.
        Optionally filter by country.
        """
        args = peers_parser.parse_args()
        country = args["country"]
        page = max(1, args["page"])
        per_page = min(100, max(1, args["per_page"]))

        query = Peer.select()

        if country:
            query = query.where(Peer.country_code == country.upper())

        query = query.order_by(Peer.datetime.desc())
        total = query.count()
        pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, pages)
        offset = (page - 1) * per_page
        peers = query.offset(offset).limit(per_page)

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "peers": [serialize_peer(p) for p in peers],
        }


@ns_peers.route("/<string:peer_url>")
@ns_peers.param("peer_url", "The peer URL (URL-encoded, e.g. http%3A%2F%2Fhost%3Aport)")
class PeerDetail(Resource):
    @ns_peers.doc("get_peer")
    @ns_peers.marshal_with(peer_model)
    @ns_peers.response(404, "Peer not found")
    def get(self, peer_url):
        """Get details for a specific peer by URL."""
        from urllib.parse import unquote
        decoded_url = unquote(peer_url)
        try:
            peer = Peer.get(Peer.url == decoded_url)
        except Peer.DoesNotExist:
            api.abort(404, f"Peer not found: {decoded_url}")
        return serialize_peer(peer)
