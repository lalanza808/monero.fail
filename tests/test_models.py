"""
Tests for model behavior and URL handling in xmrnodes/models.py.
Uses an in-memory SQLite database.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from peewee import SqliteDatabase
from xmrnodes.models import Node, HealthCheck, Peer, LWS, LWSHealthCheck


# Use in-memory DB for tests
test_db = SqliteDatabase(":memory:")


@pytest.fixture(autouse=True)
def setup_db():
    test_db.bind([Node, HealthCheck, Peer, LWS, LWSHealthCheck])
    test_db.connect()
    test_db.create_tables([Node, HealthCheck, Peer, LWS, LWSHealthCheck])
    yield
    test_db.drop_tables([Node, HealthCheck, Peer, LWS, LWSHealthCheck])
    test_db.close()


class TestNodeModel:
    def test_create_ipv4_node(self):
        node = Node.create(url="http://1.2.3.4:18081")
        assert node.url == "http://1.2.3.4:18081"
        assert node.available is False
        assert node.validated is False

    def test_create_fqdn_node(self):
        node = Node.create(url="http://node.example.com:18081")
        assert node.url == "http://node.example.com:18081"

    def test_create_ipv6_node(self):
        """IPv6 URLs fit in the existing CharField."""
        node = Node.create(url="http://[2001:db8::1]:18081")
        assert node.url == "http://[2001:db8::1]:18081"
        fetched = Node.get(Node.url == "http://[2001:db8::1]:18081")
        assert fetched.id == node.id

    def test_url_uniqueness(self):
        Node.create(url="http://1.2.3.4:18081")
        with pytest.raises(Exception):
            Node.create(url="http://1.2.3.4:18081")

    def test_get_netloc_ipv4(self):
        node = Node.create(url="http://1.2.3.4:18081")
        assert node.get_netloc() == "1.2.3.4:18081"

    def test_get_netloc_ipv6(self):
        node = Node.create(url="http://[2001:db8::1]:18081")
        assert node.get_netloc() == "[2001:db8::1]:18081"

    def test_get_netloc_fqdn(self):
        node = Node.create(url="https://node.example.com:18089")
        assert node.get_netloc() == "node.example.com:18089"


class TestHealthCheckModel:
    def test_create_health_check(self):
        node = Node.create(url="http://1.2.3.4:18081")
        hc = HealthCheck.create(node=node, health=True)
        assert hc.node.id == node.id
        assert hc.health is True

    def test_get_failed_checks(self):
        node = Node.create(url="http://1.2.3.4:18081")
        HealthCheck.create(node=node, health=True)
        HealthCheck.create(node=node, health=False)
        HealthCheck.create(node=node, health=False)
        assert node.get_failed_checks().count() == 2

    def test_get_all_checks(self):
        node = Node.create(url="http://1.2.3.4:18081")
        HealthCheck.create(node=node, health=True)
        HealthCheck.create(node=node, health=False)
        assert node.get_all_checks().count() == 2

    def test_auto_delete_threshold(self):
        """Node should be deletable when all checks fail and count > 15."""
        node = Node.create(url="http://1.2.3.4:18081", validated=True)
        for _ in range(16):
            HealthCheck.create(node=node, health=False)
        failed = node.get_failed_checks().count()
        total = node.get_all_checks().count()
        assert failed == total
        assert total > 15
        # This condition triggers deletion in check_node
        assert failed == total and total > 15

    def test_no_delete_when_some_pass(self):
        """Node should not be deleted if some checks pass."""
        node = Node.create(url="http://1.2.3.4:18081", validated=True)
        for _ in range(15):
            HealthCheck.create(node=node, health=False)
        HealthCheck.create(node=node, health=True)
        failed = node.get_failed_checks().count()
        total = node.get_all_checks().count()
        assert failed != total


class TestPeerModel:
    def test_create_peer_ipv4(self):
        peer = Peer.create(url="http://1.2.3.4:18080")
        assert peer.hostname == "1.2.3.4"
        assert peer.port == 18080

    def test_create_peer_ipv6(self):
        """IPv6 peer URLs should work with urlparse-based properties."""
        peer = Peer.create(url="http://[2001:db8::1]:18080")
        assert peer.hostname == "2001:db8::1"
        assert peer.port == 18080

    def test_get_ip_ipv4(self):
        peer = Peer.create(url="http://1.2.3.4:18080")
        assert peer.get_ip() == "1.2.3.4"

    def test_get_ip_ipv6(self):
        peer = Peer.create(url="http://[2001:db8::1]:18080")
        assert peer.get_ip() == "2001:db8::1"

    def test_hours_elapsed(self):
        peer = Peer.create(
            url="http://1.2.3.4:18080",
            datetime=datetime.utcnow() - timedelta(hours=5)
        )
        assert 4.9 < peer.hours_elapsed() < 5.1


class TestLWSModel:
    def test_create_lws(self):
        lws = LWS.create(url="https://lws.example.com")
        assert lws.url == "https://lws.example.com"
        assert lws.available is False
        assert lws.validated is False

    def test_create_lws_with_details(self):
        lws = LWS.create(
            url="https://lws.example.com",
            contact="admin@example.com",
            details_url="https://github.com/example/lws",
        )
        assert lws.contact == "admin@example.com"
        assert lws.details_url == "https://github.com/example/lws"

    def test_url_uniqueness(self):
        LWS.create(url="https://lws.example.com")
        with pytest.raises(Exception):
            LWS.create(url="https://lws.example.com")

    def test_get_netloc(self):
        lws = LWS.create(url="https://lws.example.com:8443")
        assert lws.get_netloc() == "lws.example.com:8443"

    def test_server_fields(self):
        lws = LWS.create(
            url="https://lws.example.com",
            server_type="monero-lws",
            server_version="1.1-alpha",
            blockchain_height=3768795,
            api_version=65543,
            max_subaddresses=200,
            network_type="main",
        )
        assert lws.server_type == "monero-lws"
        assert lws.server_version == "1.1-alpha"
        assert lws.blockchain_height == 3768795
        assert lws.api_version == 65543
        assert lws.max_subaddresses == 200
        assert lws.network_type == "main"


class TestLWSHealthCheckModel:
    def test_create_lws_health_check(self):
        lws = LWS.create(url="https://lws.example.com")
        hc = LWSHealthCheck.create(lws=lws, health=True)
        assert hc.lws.id == lws.id
        assert hc.health is True

    def test_get_failed_checks(self):
        lws = LWS.create(url="https://lws.example.com")
        LWSHealthCheck.create(lws=lws, health=True)
        LWSHealthCheck.create(lws=lws, health=False)
        LWSHealthCheck.create(lws=lws, health=False)
        assert lws.get_failed_checks().count() == 2

    def test_get_all_checks(self):
        lws = LWS.create(url="https://lws.example.com")
        LWSHealthCheck.create(lws=lws, health=True)
        LWSHealthCheck.create(lws=lws, health=False)
        assert lws.get_all_checks().count() == 2

    def test_auto_delete_threshold(self):
        """LWS should be deletable when all checks fail and count > 15."""
        lws = LWS.create(url="https://lws.example.com", validated=True)
        for _ in range(16):
            LWSHealthCheck.create(lws=lws, health=False)
        failed = lws.get_failed_checks().count()
        total = lws.get_all_checks().count()
        assert failed == total
        assert total > 15
