"""
Tests for URL validation regex used in node submission.
Tests current IPv4/FQDN behavior and documents expected IPv6 behavior for the refactor.
"""

import re
import pytest


# Current regex from routes/meta.py
CURRENT_REGEX = re.compile(
    r"^(?:http)s?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"\[[\da-fA-F:.]+\])"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


class TestCurrentRegexAccepts:
    """URLs that the current regex should accept."""

    @pytest.mark.parametrize("url", [
        "http://192.168.1.1:18081",
        "http://10.0.0.1:18081",
        "https://1.2.3.4:18089",
        "http://255.255.255.255:18081",
        "http://0.0.0.0:18081",
    ])
    def test_ipv4_with_port(self, url):
        assert CURRENT_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://192.168.1.1",
        "https://10.0.0.1",
    ])
    def test_ipv4_without_port(self, url):
        assert CURRENT_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://node.monero.fail:18081",
        "https://xmr.example.com:18089",
        "http://my-node.example.org:18081",
        "http://sub.domain.example.com:18081",
    ])
    def test_fqdn_with_port(self, url):
        assert CURRENT_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://node.monero.fail",
        "https://xmr.example.com",
    ])
    def test_fqdn_without_port(self, url):
        assert CURRENT_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://localhost",
        "http://localhost:18081",
    ])
    def test_localhost(self, url):
        assert CURRENT_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://example1234567890.onion:18081",
        "http://somethingsomething.i2p:18081",
    ])
    def test_tor_i2p(self, url):
        assert CURRENT_REGEX.match(url)


class TestCurrentRegexRejects:
    """URLs that the current regex should reject."""

    @pytest.mark.parametrize("url", [
        "",
        "not-a-url",
        "ftp://192.168.1.1:18081",
        "192.168.1.1:18081",
        "http://",
        "http:// spaces.com:18081",
        "http://:18081",
    ])
    def test_invalid_urls(self, url):
        assert not CURRENT_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://[::1]:18081",
        "http://[2001:db8::1]:18081",
        "https://[2604:a880:2:d0::1]:18089",
    ])
    def test_ipv6_accepted(self, url):
        """IPv6 URLs are now accepted."""
        assert CURRENT_REGEX.match(url)


class TestCurrentRegexKnownBugs:
    """Documents known issues with the current regex."""

    @pytest.mark.parametrize("url", [
        "http://999.999.999.999:18081",
        "http://256.1.1.1:18081",
        "http://300.400.500.600:18081",
    ])
    def test_accepts_invalid_ipv4_octets(self, url):
        """Bug: regex allows octets > 255."""
        assert CURRENT_REGEX.match(url)


class TestIPv6Regex:
    """Tests for the proposed IPv6-capable regex."""

    IPV6_REGEX = re.compile(
        r"^(?:http)s?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"\[[\da-fA-F:.]+\])"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    @pytest.mark.parametrize("url", [
        "http://[::1]:18081",
        "http://[2001:db8::1]:18081",
        "https://[2604:a880:2:d0::1]:18089",
        "http://[fe80::1]:18081",
        "http://[::ffff:192.0.2.1]:18081",
    ])
    def test_ipv6_with_port(self, url):
        assert self.IPV6_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://[::1]",
        "http://[2001:db8::1]",
    ])
    def test_ipv6_without_port(self, url):
        assert self.IPV6_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://2001:db8::1:18081",  # missing brackets
        "http://[]:18081",            # empty brackets
    ])
    def test_ipv6_invalid_formats(self, url):
        assert not self.IPV6_REGEX.match(url)

    @pytest.mark.parametrize("url", [
        "http://192.168.1.1:18081",
        "http://node.example.com:18081",
        "http://localhost:18081",
    ])
    def test_still_accepts_ipv4_and_fqdn(self, url):
        """Ensure the new regex doesn't break existing functionality."""
        assert self.IPV6_REGEX.match(url)
