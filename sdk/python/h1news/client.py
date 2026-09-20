"""Sync and async clients for the H1 News API.

Every method maps to one endpoint and returns the API's JSON unchanged, so the
reference at https://api.heliusone.com/docs is the reference for return shapes.
Filter arguments take Python-native values (lists for comma-separated params,
datetimes for ISO bounds) and are encoded here.

One API call = one HTTP request, however many articles it returns. A stream
connection charges one call at connect time; pushed articles are free.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://api.heliusone.com"
USER_AGENT = f"h1news-python/{__version__}"

log = logging.getLogger("h1news")


# ── errors ────────────────────────────────────────────────────────────────────

class H1NewsError(Exception):
    """Any non-2xx answer. `status` and `detail` carry what the API said."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class AuthError(H1NewsError):
    """401 — missing or invalid API key."""


class PlanLimitError(H1NewsError):
    """403 — the request needs a higher plan (multi-ticker, deep history,
    paging past the Basic cap, or the WebSocket stream)."""


class RateLimitError(H1NewsError):
    """429 — per-minute rate limit or monthly quota exhausted. `retry_after`
    is the server's hint in seconds when it sent one."""

    def __init__(self, status: int, detail: str, retry_after: float | None) -> None:
        super().__init__(status, detail)
        self.retry_after = retry_after


def _raise_for(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text
    if isinstance(detail, list):  # FastAPI validation errors
        detail = "; ".join(f"{'.'.join(map(str, e.get('loc', [])))}: {e.get('msg')}" for e in detail)
    if resp.status_code == 401:
        raise AuthError(401, detail)
    if resp.status_code == 403:
        raise PlanLimitError(403, detail)
    if resp.status_code == 429:
        ra = resp.headers.get("Retry-After")
        raise RateLimitError(429, detail, float(ra) if ra else None)
    raise H1NewsError(resp.status_code, str(detail))


# ── query encoding ────────────────────────────────────────────────────────────

def _encode(params: dict[str, Any]) -> dict[str, str]:
    """Drop Nones, join lists with commas, ISO-format datetimes, lower-case bools."""
    out: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, (list, tuple, set, frozenset)):
            if value:
                out[key] = ",".join(str(v) for v in value)
        else:
            out[key] = str(value)
    return out


def _news_params(
    ticker, match, collection, source, exclude_source, type, category,
    exclude_category, language, region, sentiment, search, date, since, until,
    since_id, sort, news_id, fallback, format, limit, offset,
) -> dict[str, str]:
    return _encode({
        "ticker": ticker, "match": match, "collection": collection,
        "source": source, "exclude_source": exclude_source, "type": type,
        "category": category, "exclude_category": exclude_category,
        "language": language, "region": region, "sentiment": sentiment,
        "search": search, "date": date, "since": since, "until": until,
        "since_id": since_id, "sort": sort, "news_id": news_id,
        "fallback": fallback, "format": format, "limit": limit, "offset": offset,
    })


# ── shared method bodies ──────────────────────────────────────────────────────

class _Endpoints:
    """Endpoint signatures shared by the sync and async clients. Each method
    returns (path, params) — the transport layer does the request."""

    @staticmethod
    def news(
        ticker: str | Sequence[str] | None = None, *,
        match: str | None = None,
        collection: str | None = None,
        source: str | Sequence[str] | None = None,
        exclude_source: str | Sequence[str] | None = None,
        type: str | None = None,
        category: str | Sequence[str] | None = None,
        exclude_category: str | Sequence[str] | None = None,
        language: str | Sequence[str] | None = None,
        region: str | Sequence[str] | None = None,
        sentiment: str | None = None,
        search: str | None = None,
        date: str | None = None,
        since: datetime | str | None = None,
        until: datetime | str | None = None,
        since_id: int | None = None,
        sort: str | None = None,
        news_id: int | Sequence[int] | None = None,
        fallback: bool | None = None,
        format: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ):
        return "/v1/news", _news_params(
            ticker, match, collection, source, exclude_source, type, category,
            exclude_category, language, region, sentiment, search, date, since,
            until, since_id, sort, news_id, fallback, format, limit, offset,
        )

    @staticmethod
    def general(**kw):
        return "/v1/news/general", _encode(kw)

    @staticmethod
    def earnings(ticker=None, **kw):
        return "/v1/news/earnings", _encode({"ticker": ticker, **kw})

    @staticmethod
    def halts(ticker=None, **kw):
        return "/v1/news/halts", _encode({"ticker": ticker, **kw})

    @staticmethod
    def filings(ticker=None, *, form=None, **kw):
        return "/v1/news/filings", _encode({"ticker": ticker, "form": form, **kw})

    @staticmethod
    def macro(*, source=None, **kw):
        return "/v1/news/macro", _encode({"source": source, **kw})

    @staticmethod
    def category(name: str, **kw):
        return f"/v1/news/category/{name}", _encode(kw)

    @staticmethod
    def article(article_id: int):
        return f"/v1/news/{int(article_id)}", {}

    @staticmethod
    def usage():
        return "/v1/usage", {}

    @staticmethod
    def tickers(search: str | None = None, limit: int | None = None):
        return "/v1/tickers", _encode({"search": search, "limit": limit})

    @staticmethod
    def sources(active_only: bool | None = None):
        return "/v1/sources", _encode({"active_only": active_only})

    @staticmethod
    def categories():
        return "/v1/categories", {}

    @staticmethod
    def top_mentioned(date: str | None = None, limit: int | None = None):
        return "/v1/top-mentioned", _encode({"date": date, "limit": limit})

    @staticmethod
    def sentiment(ticker: str | None = None, date: str | None = None):
        return "/v1/sentiment", _encode({"ticker": ticker, "date": date})

    @staticmethod
    def earnings_calendar(ticker: str | None = None, days: int | None = None):
        return "/v1/earnings-calendar", _encode({"ticker": ticker, "days": days})

    @staticmethod
    def ratings(ticker: str):
        return "/v1/ratings", _encode({"ticker": ticker})

    @staticmethod
    def sundown_digest(refresh: bool | None = None):
        return "/v1/sundown-digest", _encode({"refresh": refresh})


_STREAM_FILTERS = (
    "tickers", "sources", "exclude_sources", "types", "exclude_types",
    "categories", "exclude_categories", "languages", "regions",
)


def _stream_url(base_url: str, auth: dict[str, str], filters: dict[str, Any]) -> str:
    ws_base = base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    params = {**auth, **_encode({k: filters.get(k) for k in _STREAM_FILTERS})}
    return f"{ws_base}/v1/stream?{urlencode(params)}"


# ── sync client ───────────────────────────────────────────────────────────────

class H1News:
    """Synchronous client. Use as a context manager to reuse the connection pool.

        news = H1News("sk_...")
        page = news.news(ticker="NVDA", date="today")
        page["total"], page["results"][0]["title"]
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 20.0,
        max_retries: int = 2,
        anthropic_key: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required — get one at https://heliusone.com/newsapi")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.anthropic_key = anthropic_key
        self._http = httpx.Client(
            base_url=self.base_url, timeout=timeout,
            headers={"X-API-Key": api_key, "User-Agent": USER_AGENT},
        )

    # transport
    def _get(self, path: str, params: dict[str, str], *, headers: dict | None = None) -> Any:
        attempt = 0
        while True:
            resp = self._http.get(path, params=params, headers=headers)
            if resp.status_code == 429 and attempt < self.max_retries:
                ra = resp.headers.get("Retry-After")
                delay = float(ra) if ra else min(2 ** attempt, 30) + random.random()
                log.info("rate limited on %s; retrying in %.1fs", path, delay)
                time.sleep(delay)
                attempt += 1
                continue
            _raise_for(resp)
            if params.get("format") == "csv":
                return resp.text
            return resp.json()

    def _post(self, path: str) -> Any:
        resp = self._http.post(path)
        _raise_for(resp)
        return resp.json()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "H1News":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # endpoints
    def news(self, ticker=None, **kw) -> dict:
        """GET /v1/news — history with every filter. Returns
        {"total", "page", "pages", "results": [article, ...]}."""
        return self._get(*_Endpoints.news(ticker, **kw))

    def general(self, **kw) -> dict:
        """GET /v1/news/general — market news not tied to any ticker."""
        return self._get(*_Endpoints.general(**kw))

    def earnings(self, ticker=None, **kw) -> dict:
        """GET /v1/news/earnings — results wires + earnings coverage."""
        return self._get(*_Endpoints.earnings(ticker, **kw))

    def halts(self, ticker=None, **kw) -> dict:
        """GET /v1/news/halts — Nasdaq trading halts / resumptions."""
        return self._get(*_Endpoints.halts(ticker, **kw))

    def filings(self, ticker=None, *, form=None, **kw) -> dict:
        """GET /v1/news/filings — SEC EDGAR filings; form = 8-K | 4 | S-1 | SC 13D | 10-Q."""
        return self._get(*_Endpoints.filings(ticker, form=form, **kw))

    def macro(self, *, source=None, **kw) -> dict:
        """GET /v1/news/macro — central banks & economy."""
        return self._get(*_Endpoints.macro(source=source, **kw))

    def category(self, name: str, **kw) -> dict:
        """GET /v1/news/category/{name} — any category as its own feed."""
        return self._get(*_Endpoints.category(name, **kw))

    def article(self, article_id: int) -> dict:
        """GET /v1/news/{id} — one article."""
        return self._get(*_Endpoints.article(article_id))

    def usage(self) -> dict:
        """GET /v1/usage — plan, quota and usage for this key (not metered)."""
        return self._get(*_Endpoints.usage())

    def tickers(self, search: str | None = None, limit: int | None = None) -> dict:
        """GET /v1/tickers — the SEC symbol universe; `search` is a prefix."""
        return self._get(*_Endpoints.tickers(search, limit))

    def sources(self, active_only: bool | None = None) -> dict:
        """GET /v1/sources — source names with counts; use with source= filters."""
        return self._get(*_Endpoints.sources(active_only))

    def categories(self) -> dict:
        """GET /v1/categories — categories in the feed, with counts."""
        return self._get(*_Endpoints.categories())

    def top_mentioned(self, date: str | None = None, limit: int | None = None) -> dict:
        """GET /v1/top-mentioned — most-mentioned tickers over a preset window."""
        return self._get(*_Endpoints.top_mentioned(date, limit))

    def sentiment(self, ticker: str | None = None, date: str | None = None) -> dict:
        """GET /v1/sentiment — daily sentiment breakdown for a ticker or the market."""
        return self._get(*_Endpoints.sentiment(ticker, date))

    def earnings_calendar(self, ticker: str | None = None, days: int | None = None) -> dict:
        """GET /v1/earnings-calendar — upcoming earnings dates."""
        return self._get(*_Endpoints.earnings_calendar(ticker, days))

    def ratings(self, ticker: str) -> dict:
        """GET /v1/ratings — analyst buy/hold/sell trends."""
        return self._get(*_Endpoints.ratings(ticker))

    def sundown_digest(self, *, refresh: bool = False, anthropic_key: str | None = None) -> dict:
        """GET /v1/sundown-digest — end-of-day recap. The cached digest needs no
        Anthropic key; generating one (cache miss or refresh=True) uses the key
        you pass here (or the client's `anthropic_key`) for a single call."""
        key = anthropic_key or self.anthropic_key
        headers = {"X-Anthropic-Key": key} if key else None
        return self._get(*_Endpoints.sundown_digest(refresh or None), headers=headers)

    def stream_token(self) -> dict:
        """POST /v1/stream/token — {"token", "expires_in", "ws_url"} for a browser
        client, so your key never leaves the server. Pro plan."""
        return self._post("/v1/stream/token")

    # helpers
    def iter_news(self, ticker=None, *, page_size: int = 200, max_items: int | None = None, **kw) -> Iterator[dict]:
        """Walk /v1/news page by page, yielding articles. Stops at `max_items`,
        the end of the result set, or the plan's paging cap (raises
        PlanLimitError past 500 results on Basic)."""
        offset = 0
        yielded = 0
        while True:
            page = self.news(ticker, limit=page_size, offset=offset, **kw)
            results = page.get("results", [])
            for a in results:
                yield a
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            if len(results) < page_size:
                return
            offset += page_size

    def poll(self, ticker=None, *, interval: float = 30.0, since_id: int | None = None, **kw) -> Iterator[dict]:
        """Near-real-time polling for plans without the stream: yields only
        articles newer than the last one seen, every `interval` seconds. Each
        poll is one API call — 30s is ~2,900 calls/month per poller."""
        last = since_id
        if last is None:
            first = self.news(ticker, limit=1, **kw).get("results", [])
            last = first[0]["id"] if first else 0
        while True:
            page = self.news(ticker, since_id=last, sort="oldest", limit=200, **kw)
            for a in page.get("results", []):
                last = max(last, a["id"])
                yield a
            time.sleep(interval)


# ── async client ──────────────────────────────────────────────────────────────

class AsyncH1News:
    """Async client with the same methods as `H1News`, plus `stream()`.

        async with AsyncH1News("sk_...") as news:
            async for a in news.stream(tickers=["AAPL"], categories=["halts", "earnings"]):
                ...
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 20.0,
        max_retries: int = 2,
        anthropic_key: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required — get one at https://heliusone.com/newsapi")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.anthropic_key = anthropic_key
        self._http = httpx.AsyncClient(
            base_url=self.base_url, timeout=timeout,
            headers={"X-API-Key": api_key, "User-Agent": USER_AGENT},
        )

    async def _get(self, path: str, params: dict[str, str], *, headers: dict | None = None) -> Any:
        attempt = 0
        while True:
            resp = await self._http.get(path, params=params, headers=headers)
            if resp.status_code == 429 and attempt < self.max_retries:
                ra = resp.headers.get("Retry-After")
                delay = float(ra) if ra else min(2 ** attempt, 30) + random.random()
                await asyncio.sleep(delay)
                attempt += 1
                continue
            _raise_for(resp)
            if params.get("format") == "csv":
                return resp.text
            return resp.json()

    async def _post(self, path: str) -> Any:
        resp = await self._http.post(path)
        _raise_for(resp)
        return resp.json()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncH1News":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def news(self, ticker=None, **kw) -> dict:
        return await self._get(*_Endpoints.news(ticker, **kw))

    async def general(self, **kw) -> dict:
        return await self._get(*_Endpoints.general(**kw))

    async def earnings(self, ticker=None, **kw) -> dict:
        return await self._get(*_Endpoints.earnings(ticker, **kw))

    async def halts(self, ticker=None, **kw) -> dict:
        return await self._get(*_Endpoints.halts(ticker, **kw))

    async def filings(self, ticker=None, *, form=None, **kw) -> dict:
        return await self._get(*_Endpoints.filings(ticker, form=form, **kw))

    async def macro(self, *, source=None, **kw) -> dict:
        return await self._get(*_Endpoints.macro(source=source, **kw))

    async def category(self, name: str, **kw) -> dict:
        return await self._get(*_Endpoints.category(name, **kw))

    async def article(self, article_id: int) -> dict:
        return await self._get(*_Endpoints.article(article_id))

    async def usage(self) -> dict:
        return await self._get(*_Endpoints.usage())

    async def tickers(self, search=None, limit=None) -> dict:
        return await self._get(*_Endpoints.tickers(search, limit))

    async def sources(self, active_only=None) -> dict:
        return await self._get(*_Endpoints.sources(active_only))

    async def categories(self) -> dict:
        return await self._get(*_Endpoints.categories())

    async def top_mentioned(self, date=None, limit=None) -> dict:
        return await self._get(*_Endpoints.top_mentioned(date, limit))

    async def sentiment(self, ticker=None, date=None) -> dict:
        return await self._get(*_Endpoints.sentiment(ticker, date))

    async def earnings_calendar(self, ticker=None, days=None) -> dict:
        return await self._get(*_Endpoints.earnings_calendar(ticker, days))

    async def ratings(self, ticker: str) -> dict:
        return await self._get(*_Endpoints.ratings(ticker))

    async def sundown_digest(self, *, refresh: bool = False, anthropic_key: str | None = None) -> dict:
        key = anthropic_key or self.anthropic_key
        headers = {"X-Anthropic-Key": key} if key else None
        return await self._get(*_Endpoints.sundown_digest(refresh or None), headers=headers)

    async def stream_token(self) -> dict:
        return await self._post("/v1/stream/token")

    async def stream(
        self,
        *,
        tickers: Sequence[str] | None = None,
        sources: Sequence[str] | None = None,
        exclude_sources: Sequence[str] | None = None,
        types: Sequence[str] | None = None,
        exclude_types: Sequence[str] | None = None,
        categories: Sequence[str] | None = None,
        exclude_categories: Sequence[str] | None = None,
        languages: Sequence[str] | None = None,
        regions: Sequence[str] | None = None,
        token: str | None = None,
        backfill: bool = True,
        ping_interval: float = 30.0,
        max_backoff: float = 30.0,
    ) -> AsyncIterator[dict]:
        """Live articles as they are ingested (Pro plan).

        Reconnects with exponential backoff when the socket drops (redeploys,
        network blips, Cloud Run's ~60-minute connection cap) and, when
        `backfill` is on, replays anything published in the gap via
        `/v1/news?since_id=` so the sequence you see is gapless. Pass `token`
        (from `stream_token()`) instead of using the key — the browser pattern.
        Raises PlanLimitError immediately if the key's plan has no stream.
        """
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pip install websockets to use stream()") from exc

        filters = {
            "tickers": tickers, "sources": sources, "exclude_sources": exclude_sources,
            "types": types, "exclude_types": exclude_types, "categories": categories,
            "exclude_categories": exclude_categories, "languages": languages, "regions": regions,
        }
        auth = {"token": token} if token else {"api_key": self.api_key}
        url = _stream_url(self.base_url, auth, filters)

        # REST-side equivalents for backfill (the stream and /v1/news share names
        # for everything but plural/singular).
        rest_filters = _encode({
            "ticker": tickers, "source": sources, "exclude_source": exclude_sources,
            "type": types[0] if types and len(types) == 1 else None,
            "category": categories, "exclude_category": exclude_categories,
            "language": languages, "region": regions,
        })

        last_id: int | None = None
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(url, ping_interval=None, max_size=2**20) as ws:
                    backoff = 1.0
                    if backfill and last_id is not None:
                        page = await self._get("/v1/news", {**rest_filters, "since_id": str(last_id), "sort": "oldest", "limit": "200"})
                        for a in page.get("results", []):
                            last_id = max(last_id, a["id"])
                            yield a

                    async def _keepalive() -> None:
                        while True:
                            await asyncio.sleep(ping_interval)
                            await ws.send(json.dumps({"action": "ping"}))

                    ka = asyncio.create_task(_keepalive())
                    try:
                        async for raw in ws:
                            try:
                                msg = json.loads(raw)
                            except ValueError:
                                continue
                            if not isinstance(msg, dict):
                                continue
                            if "pong" in msg or "ack" in msg:
                                continue
                            if "error" in msg:
                                if msg.get("code") == "plan_upgrade_required":
                                    raise PlanLimitError(403, msg["error"])
                                log.warning("stream error frame: %s", msg)
                                continue
                            if "id" in msg:
                                last_id = max(last_id or 0, msg["id"])
                            yield msg
                    finally:
                        ka.cancel()
            except PlanLimitError:
                raise
            except (websockets.exceptions.InvalidStatus, websockets.exceptions.InvalidHandshake) as exc:  # type: ignore[attr-defined]
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in (401, 403):
                    raise AuthError(status, "stream rejected the credentials") from exc
                log.warning("stream handshake failed (%s); retrying in %.0fs", exc, backoff)
            except websockets.exceptions.ConnectionClosedError as exc:  # type: ignore[attr-defined]
                if exc.code == 1008:
                    raise AuthError(401, "invalid API key or token") from exc
                if exc.code == 4403:
                    raise PlanLimitError(403, "the live stream is a Pro-plan feature") from exc
                log.info("stream closed (%s); reconnecting in %.0fs", exc.code, backoff)
            except (OSError, asyncio.TimeoutError) as exc:
                log.info("stream connection error (%s); reconnecting in %.0fs", exc, backoff)
            await asyncio.sleep(backoff + random.random())
            backoff = min(backoff * 2, max_backoff)
