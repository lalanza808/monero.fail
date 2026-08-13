"""
Tests for helper functions in xmrnodes/helpers.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse

from xmrnodes.helpers import is_onion, is_i2p


class TestIsOnion:
    def test_onion_http(self):
        assert is_onion("http://abc123.onion:18081") is True

    def test_onion_https(self):
        assert is_onion("https://abc123.onion:18081") is True

    def test_onion_no_port(self):
        assert is_onion("http://abc123.onion") is True

    def test_not_onion(self):
        assert is_onion("http://example.com:18081") is False

    def test_not_onion_ipv4(self):
        assert is_onion("http://1.2.3.4:18081") is False

    def test_empty_string(self):
        assert is_onion("") is False


class TestIsI2p:
    def test_i2p_http(self):
        assert is_i2p("http://abc123.i2p:18081") is True

    def test_i2p_no_port(self):
        assert is_i2p("http://abc123.i2p") is True

    def test_not_i2p(self):
        assert is_i2p("http://example.com:18081") is False

    def test_empty_string(self):
        assert is_i2p("") is False


class TestIsOnionIPv6:
    """After refactor, is_onion should still work with IPv6 URLs."""

    def test_ipv6_not_onion(self):
        assert is_onion("http://[2001:db8::1]:18081") is False


class TestIsI2pIPv6:
    """After refactor, is_i2p should still work with IPv6 URLs."""

    def test_ipv6_not_i2p(self):
        assert is_i2p("http://[2001:db8::1]:18081") is False


class TestHostExtraction:
    """
    Tests documenting the correct way to extract hosts from URLs.
    The codebase uses .split(':')[0] in places which breaks on IPv6.
    urlparse().hostname is the correct approach.
    """

    @pytest.mark.parametrize("url,expected_host", [
        ("http://192.168.1.1:18081", "192.168.1.1"),
        ("http://example.com:18081", "example.com"),
        ("http://[2001:db8::1]:18081", "2001:db8::1"),
        ("http://[::1]:18081", "::1"),
        ("http://localhost:18081", "localhost"),
        ("https://node.monero.fail:18089", "node.monero.fail"),
    ])
    def test_urlparse_hostname(self, url, expected_host):
        """urlparse().hostname correctly handles all URL types including IPv6."""
        assert urlparse(url).hostname == expected_host

    @pytest.mark.parametrize("url,expected_port", [
        ("http://192.168.1.1:18081", 18081),
        ("http://[2001:db8::1]:18081", 18081),
        ("http://example.com", None),
    ])
    def test_urlparse_port(self, url, expected_port):
        assert urlparse(url).port == expected_port

    def test_split_colon_breaks_ipv6(self):
        """Documents the bug: splitting on ':' fails for IPv6 netloc."""
        url = "http://[2001:db8::1]:18081"
        netloc = urlparse(url).netloc
        # This is the broken pattern used in helpers.py get_geoip
        broken_host = netloc.split(':')[0]
        # It gives "[2001" instead of "2001:db8::1"
        assert broken_host == "[2001"
        # The correct way:
        correct_host = urlparse(url).hostname
        assert correct_host == "2001:db8::1"


class TestMakeRequest:
    """Tests for make_request proxy routing."""

    @patch("xmrnodes.helpers.r_get")
    def test_clearnet_no_proxy(self, mock_get):
        from xmrnodes.helpers import make_request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        make_request("http://1.2.3.4:18081")
        _, kwargs = mock_get.call_args
        assert kwargs["proxies"] is None
        assert kwargs["timeout"] == 10

    @patch("xmrnodes.helpers.r_get")
    def test_onion_uses_tor_proxy(self, mock_get):
        from xmrnodes.helpers import make_request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        make_request("http://something.onion:18081")
        _, kwargs = mock_get.call_args
        assert "socks5h://" in kwargs["proxies"]["http"]
        assert kwargs["timeout"] == 20

    @patch("xmrnodes.helpers.r_get")
    def test_i2p_uses_http_proxy(self, mock_get):
        from xmrnodes.helpers import make_request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        make_request("http://something.i2p:18081")
        _, kwargs = mock_get.call_args
        assert kwargs["proxies"]["http"].startswith("http://")
        assert kwargs["timeout"] == 20

    @patch("xmrnodes.helpers.r_get")
    def test_ipv6_clearnet_no_proxy(self, mock_get):
        """After refactor: IPv6 nodes should route directly like IPv4."""
        from xmrnodes.helpers import make_request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        make_request("http://[2001:db8::1]:18081")
        _, kwargs = mock_get.call_args
        assert kwargs["proxies"] is None
        assert kwargs["timeout"] == 10


class TestGetGeoip:
    """Tests for GeoIP resolution."""

    @patch("xmrnodes.helpers.geoip2.database.Reader")
    @patch("xmrnodes.helpers.socket.gethostbyname")
    def test_resolves_fqdn(self, mock_dns, mock_reader):
        from xmrnodes.helpers import get_geoip
        mock_dns.return_value = "93.184.216.34"
        mock_reader_instance = MagicMock()
        mock_reader.return_value.__enter__ = MagicMock(return_value=mock_reader_instance)
        mock_reader.return_value.__exit__ = MagicMock(return_value=False)

        get_geoip("http://example.com:18081")
        mock_dns.assert_called_once_with("example.com")
        mock_reader_instance.city.assert_called_once_with("93.184.216.34")

    @patch("xmrnodes.helpers.geoip2.database.Reader")
    @patch("xmrnodes.helpers.socket.gethostbyname")
    def test_ipv4_direct(self, mock_dns, mock_reader):
        from xmrnodes.helpers import get_geoip
        mock_dns.return_value = "1.2.3.4"
        mock_reader_instance = MagicMock()
        mock_reader.return_value.__enter__ = MagicMock(return_value=mock_reader_instance)
        mock_reader.return_value.__exit__ = MagicMock(return_value=False)

        get_geoip("http://1.2.3.4:18081")
        mock_dns.assert_called_once_with("1.2.3.4")
        mock_reader_instance.city.assert_called_once_with("1.2.3.4")
