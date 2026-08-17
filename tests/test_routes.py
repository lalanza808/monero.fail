"""
Tests for Flask routes, focusing on the /add endpoint.
"""

import pytest
from unittest.mock import patch

from peewee import SqliteDatabase
from xmrnodes.models import Node, HealthCheck, Peer
from xmrnodes.app import app as flask_app


test_db = SqliteDatabase(":memory:")


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    test_db.bind([Node, HealthCheck, Peer])
    test_db.connect()
    test_db.create_tables([Node, HealthCheck, Peer])

    yield flask_app

    test_db.drop_tables([Node, HealthCheck, Peer])
    test_db.close()


@pytest.fixture
def client(app):
    return app.test_client()


class TestAddNode:
    """Tests for the /add POST endpoint."""

    def test_add_valid_ipv4(self, client):
        resp = client.post("/add", data={"node_url": "http://1.2.3.4:18081"}, follow_redirects=True)
        assert resp.status_code == 200
        assert Node.select().where(Node.url == "http://1.2.3.4:18081").exists()

    def test_add_valid_fqdn(self, client):
        resp = client.post("/add", data={"node_url": "http://node.example.com:18081"}, follow_redirects=True)
        assert resp.status_code == 200
        assert Node.select().where(Node.url == "http://node.example.com:18081").exists()

    def test_add_valid_https(self, client):
        resp = client.post("/add", data={"node_url": "https://node.example.com:18089"}, follow_redirects=True)
        assert resp.status_code == 200
        assert Node.select().where(Node.url == "https://node.example.com:18089").exists()

    def test_add_tor_node(self, client):
        resp = client.post("/add", data={"node_url": "http://abcdef.onion:18081"}, follow_redirects=True)
        assert resp.status_code == 200
        assert Node.select().where(Node.url == "http://abcdef.onion:18081").exists()

    def test_add_duplicate_rejected(self, client):
        client.post("/add", data={"node_url": "http://1.2.3.4:18081"}, follow_redirects=True)
        client.post("/add", data={"node_url": "http://1.2.3.4:18081"}, follow_redirects=True)
        assert Node.select().where(Node.url == "http://1.2.3.4:18081").count() == 1

    def test_add_empty_url_rejected(self, client):
        resp = client.post("/add", data={"node_url": ""}, follow_redirects=True)
        assert Node.select().count() == 0

    def test_add_invalid_url_rejected(self, client):
        resp = client.post("/add", data={"node_url": "not-a-url"}, follow_redirects=True)
        assert Node.select().count() == 0

    def test_add_ftp_rejected(self, client):
        resp = client.post("/add", data={"node_url": "ftp://1.2.3.4:18081"}, follow_redirects=True)
        assert Node.select().count() == 0

    def test_add_no_scheme_rejected(self, client):
        resp = client.post("/add", data={"node_url": "1.2.3.4:18081"}, follow_redirects=True)
        assert Node.select().count() == 0

    def test_url_normalized_lowercase(self, client):
        client.post("/add", data={"node_url": "HTTP://Node.Example.COM:18081"}, follow_redirects=True)
        assert Node.select().where(Node.url == "http://node.example.com:18081").exists()

    def test_add_ipv6_accepted(self, client):
        """IPv6 URLs are now accepted."""
        resp = client.post("/add", data={"node_url": "http://[2001:db8::1]:18081"}, follow_redirects=True)
        assert Node.select().where(Node.url == "http://[2001:db8::1]:18081").exists()


def _create_test_nodes():
    """Create a set of test nodes for API tests."""
    nodes_data = [
        {"url": "http://node1.example.com:18081", "validated": True, "available": True,
         "nettype": "mainnet", "crypto": "monero", "is_tor": False, "is_i2p": False,
         "is_ipv6": False, "web_compatible": False, "last_height": 3000000,
         "country_code": "US", "country_name": "United States", "city": "New York",
         "lat": 40.7, "lon": -74.0},
        {"url": "http://node2.example.com:18081", "validated": True, "available": True,
         "nettype": "mainnet", "crypto": "monero", "is_tor": False, "is_i2p": False,
         "is_ipv6": False, "web_compatible": True, "last_height": 3000000,
         "country_code": "DE", "country_name": "Germany", "city": "Berlin",
         "lat": 52.5, "lon": 13.4},
        {"url": "http://tornode.onion:18081", "validated": True, "available": True,
         "nettype": "mainnet", "crypto": "monero", "is_tor": True, "is_i2p": False,
         "is_ipv6": False, "web_compatible": False, "last_height": 3000000,
         "country_code": None, "country_name": None, "city": None,
         "lat": None, "lon": None},
        {"url": "http://i2pnode.i2p:18081", "validated": True, "available": True,
         "nettype": "mainnet", "crypto": "monero", "is_tor": False, "is_i2p": True,
         "is_ipv6": False, "web_compatible": False, "last_height": 3000000,
         "country_code": None, "country_name": None, "city": None,
         "lat": None, "lon": None},
        {"url": "http://wownode.example.com:34568", "validated": True, "available": True,
         "nettype": "mainnet", "crypto": "wownero", "is_tor": False, "is_i2p": False,
         "is_ipv6": False, "web_compatible": False, "last_height": 500000,
         "country_code": "FR", "country_name": "France", "city": "Paris",
         "lat": 48.9, "lon": 2.3},
        {"url": "http://down.example.com:18081", "validated": True, "available": False,
         "nettype": "mainnet", "crypto": "monero", "is_tor": False, "is_i2p": False,
         "is_ipv6": False, "web_compatible": False, "last_height": 2999990,
         "country_code": "US", "country_name": "United States", "city": "Chicago",
         "lat": 41.9, "lon": -87.6},
    ]
    for data in nodes_data:
        Node.create(**data)


class TestRestApiNodes:
    """Tests for the /api/v1/nodes/ REST endpoint."""

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_list_nodes_default(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data
        # Default filters: monero, mainnet, healthy=true
        # Should include available nodes with height > healthy_block
        assert data["total"] >= 1

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_filter_by_crypto(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/?crypto=wownero")
        data = resp.get_json()
        for node in data["nodes"]:
            assert node["crypto"] == "wownero"

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_filter_by_type_onion(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/?type=onion")
        data = resp.get_json()
        for node in data["nodes"]:
            assert node["is_tor"] is True

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_filter_by_type_i2p(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/?type=i2p")
        data = resp.get_json()
        for node in data["nodes"]:
            assert node["is_i2p"] is True

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_filter_by_type_cors(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/?type=cors")
        data = resp.get_json()
        for node in data["nodes"]:
            assert node["web_compatible"] is True

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_filter_by_country(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/?country=DE&healthy=all")
        data = resp.get_json()
        for node in data["nodes"]:
            assert node["country_code"] == "DE"

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_filter_unhealthy(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/?healthy=false")
        data = resp.get_json()
        for node in data["nodes"]:
            assert node["available"] is False or node["last_height"] <= 2999900

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_pagination(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/?per_page=1&healthy=all")
        data = resp.get_json()
        assert data["per_page"] == 1
        assert len(data["nodes"]) <= 1
        assert data["pages"] >= 1

    def test_swagger_docs_accessible(self, client):
        resp = client.get("/api/v1/docs")
        assert resp.status_code == 200

    def test_swagger_json_accessible(self, client):
        resp = client.get("/api/v1/swagger.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "paths" in data
        assert "info" in data


class TestRestApiHealth:
    """Tests for the /api/v1/health/ REST endpoint."""

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_health_list(self, mock_block, client):
        _create_test_nodes()
        # Add a health check
        node = Node.get(Node.url == "http://node1.example.com:18081")
        HealthCheck.create(node=node, health=True)
        HealthCheck.create(node=node, health=False)

        resp = client.get("/api/v1/health/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "total" in data
        # Find our node in results
        found = [n for n in data["nodes"] if n["url"] == "http://node1.example.com:18081"]
        if found:
            assert "checks" in found[0]
            assert len(found[0]["checks"]) == 2


class TestRestApiNearby:
    """Tests for the /api/v1/nodes/nearby REST endpoint."""

    @patch("xmrnodes.routes.api.get_highest_block", return_value=3000000)
    def test_nearby_nodes(self, mock_block, client):
        _create_test_nodes()
        resp = client.get("/api/v1/nodes/nearby?lat=40.7&lon=-74.0")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "total" in data
        # First result should be closest to NYC coordinates
        if data["nodes"]:
            assert "distance_km" in data["nodes"][0]
            # Results should be sorted by distance
            distances = [n["distance_km"] for n in data["nodes"]]
            assert distances == sorted(distances)

    def test_nearby_missing_params(self, client):
        resp = client.get("/api/v1/nodes/nearby")
        assert resp.status_code == 400
