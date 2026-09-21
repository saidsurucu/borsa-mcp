"""Regression tests for the get_news SSRF guard.

`get_news(news_id=...)` accepts a URL and used to pass it straight to
`httpx.get()`. These tests pin the allow-list so an arbitrary host (localhost,
cloud metadata, internal services) can no longer be fetched server-side.
"""
import asyncio
import socket
from unittest.mock import AsyncMock

import pytest

from providers.market_router import MarketRouter, validate_news_url


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8080/",
    "http://localhost/",
    "http://0.0.0.0/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/",
    "http://192.168.1.1/",
    "http://evil.example.com/",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_GET",
])
def test_validate_news_url_rejects_ssrf_targets(url):
    with pytest.raises(ValueError):
        run(validate_news_url(url))


def test_validate_news_url_allows_allowlisted_host(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("151.101.1.140", 0)),
    ])
    url = "https://finans.mynet.com/borsa/haberdetay/12345/"
    assert run(validate_news_url(url)) == url


def test_validate_news_url_blocks_private_dns_answer(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
    ])
    with pytest.raises(ValueError):
        run(validate_news_url("https://finans.mynet.com/"))


def test_get_news_detail_blocks_ssrf_without_fetching():
    router = MarketRouter()
    router._client.get_kap_haber_detayi_mynet = AsyncMock()

    with pytest.raises(ValueError):
        run(router.get_news_detail("http://127.0.0.1:8080/"))

    router._client.get_kap_haber_detayi_mynet.assert_not_called()
