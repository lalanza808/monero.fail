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
