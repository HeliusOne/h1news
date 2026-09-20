"""Offline tests for the Python SDK — httpx.MockTransport stands in for the API.

Run: cd sdk/python && pip install -e ".[dev]" && pytest
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from h1news import AsyncH1News, AuthError, H1News, PlanLimitError, RateLimitError
from h1news.client import _encode, _stream_url


def _client(handler) -> H1News:
    c = H1News("sk_test", max_retries=1)
    c._http = httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler),
                           headers={"X-API-Key": "sk_test"})
    return c


def test_encode_joins_lists_formats_datetimes_and_drops_nones() -> None:
    out = _encode({
        "ticker": ["AAPL", "TSLA"], "since": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "fallback": True, "limit": 5, "search": None, "region": [],
    })
    assert out == {"ticker": "AAPL,TSLA", "since": "2026-09-01T00:00:00+00:00", "fallback": "true", "limit": "5"}


def test_news_sends_the_documented_query_params() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["key"] = req.headers.get("x-api-key")
        return httpx.Response(200, json={"total": 1, "results": [{"id": 1}]})

    page = _client(handler).news(["AAPL", "TSLA"], match="all", category=["earnings", "halts"],
                                 sentiment="negative", date="today", limit=5)
    assert seen["key"] == "sk_test"
    assert "ticker=AAPL%2CTSLA" in seen["url"] and "match=all" in seen["url"]
    assert "category=earnings%2Chalts" in seen["url"] and "sentiment=negative" in seen["url"]
    assert page["results"][0]["id"] == 1


@pytest.mark.parametrize("status,exc", [(401, AuthError), (403, PlanLimitError), (429, RateLimitError)])
def test_status_codes_map_to_typed_errors(status, exc) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "nope"}, headers={"Retry-After": "0"})

    with pytest.raises(exc) as info:
        _client(handler).usage()
    assert info.value.status == status and info.value.detail == "nope"


def test_rate_limit_is_retried_once_then_raised() -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"detail": "slow down"}, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    assert _client(handler).usage() == {"ok": True}
    assert calls["n"] == 2


def test_iter_news_pages_until_a_short_page() -> None:
    pages = {0: [{"id": i} for i in range(3)], 3: [{"id": 3}]}

    def handler(req: httpx.Request) -> httpx.Response:
        offset = int(req.url.params.get("offset", 0))
        return httpx.Response(200, json={"results": pages.get(offset, [])})

    ids = [a["id"] for a in _client(handler).iter_news("AAPL", page_size=3)]
    assert ids == [0, 1, 2, 3]


def test_sundown_digest_sends_the_anthropic_key_only_when_given() -> None:
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.headers.get("x-anthropic-key"))
        return httpx.Response(200, json={})

    c = _client(handler)
    c.sundown_digest()
    c.sundown_digest(anthropic_key="ak")
    assert seen == [None, "ak"]


def test_stream_url_carries_auth_and_plural_filters() -> None:
    url = _stream_url("https://api.heliusone.com", {"api_key": "k"},
                      {"tickers": ["AAPL"], "categories": ["halts", "earnings"], "regions": None})
    assert url.startswith("wss://api.heliusone.com/v1/stream?")
    assert "api_key=k" in url and "tickers=AAPL" in url and "categories=halts%2Cearnings" in url
    assert "regions" not in url


async def test_async_client_shares_the_endpoint_table() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/news/halts" and req.url.params["ticker"] == "TSLA"
        return httpx.Response(200, json={"results": []})

    c = AsyncH1News("sk_test")
    c._http = httpx.AsyncClient(base_url="https://api.test", transport=httpx.MockTransport(handler))
    assert await c.halts("TSLA") == {"results": []}
    await c.aclose()
