"""MCP server exposing the H1 News API as tools.

Configuration: H1NEWS_API_KEY (required), H1NEWS_BASE_URL (optional),
ANTHROPIC_API_KEY (optional — only for generating the Sundown Digest on a cache
miss; the cached digest needs no key).

Claude Desktop (claude_desktop_config.json):

    {"mcpServers": {"h1news": {"command": "h1news-mcp",
                               "env": {"H1NEWS_API_KEY": "sk_..."}}}}

Every tool returns compact JSON — title, source, time, tickers, sentiment,
category, url — so a page of results costs a few hundred tokens, and the
`url` is there for the model to open the article when it needs the body.
"""
from __future__ import annotations

import json
import os
from typing import Optional

try:  # mcp >= 2.0 renamed FastMCP to MCPServer; support both.
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

from h1news import H1News, H1NewsError

mcp = FastMCP(
    "H1 News",
    instructions=(
        "Real-time financial news from 135+ sources, tagged with tickers and scored "
        "for sentiment. Use search_news for anything general; ticker_news for one "
        "symbol; trading_halts, sec_filings and regulatory_actions for event feeds; "
        "market_sentiment and top_mentioned for aggregates. Dates are presets: today, "
        "yesterday, last7days, last30days. Times are UTC."
    ),
)

_client: H1News | None = None


def client() -> H1News:
    global _client
    if _client is None:
        key = os.environ.get("H1NEWS_API_KEY")
        if not key:
            raise RuntimeError("Set H1NEWS_API_KEY — get a key at https://heliusone.com/newsapi")
        _client = H1News(
            key,
            base_url=os.environ.get("H1NEWS_BASE_URL", "https://api.heliusone.com"),
            anthropic_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
    return _client


def _compact(page: dict) -> str:
    rows = [
        {
            "id": a["id"], "title": a["title"], "source": a["source"],
            "published_at": a["published_at"], "tickers": a.get("tickers", []),
            "sentiment": a.get("sentiment", {}).get("label"),
            "category": a.get("category"), "url": a["url"],
        }
        for a in page.get("results", [])
    ]
    return json.dumps({"total": page.get("total", len(rows)), "results": rows}, ensure_ascii=False)


def _guard(fn):
    """Turn API errors into a message the model can act on (upgrade, retry)."""
    try:
        return fn()
    except H1NewsError as exc:
        return json.dumps({"error": exc.detail, "status": exc.status})


@mcp.tool()
def search_news(
    query: Optional[str] = None,
    ticker: Optional[str] = None,
    category: Optional[str] = None,
    sentiment: Optional[str] = None,
    region: Optional[str] = None,
    language: Optional[str] = None,
    source: Optional[str] = None,
    date: str = "last7days",
    limit: int = 10,
) -> str:
    """Search financial news. query: full-text, supports AND / OR ("Elon Musk AND
    Tesla"). ticker: one symbol (Pro keys may pass several comma-separated).
    category: markets | earnings | macro | world | commodities | forex | crypto |
    halts | filings | regulatory. sentiment: positive | negative | neutral.
    region: us | uk | eu | jp | br | mx | latam | ca | au | in | cn | asia | global.
    language: ISO code such as en, pt, es. source: exact name from list_sources.
    date: today | yesterday | last7days | last30days."""
    return _guard(lambda: _compact(client().news(
        ticker, search=query, category=category, sentiment=sentiment, region=region,
        language=language, source=source, date=date, limit=max(1, min(limit, 50)),
    )))


@mcp.tool()
def ticker_news(ticker: str, date: str = "last7days", sentiment: Optional[str] = None, limit: int = 10) -> str:
    """Latest news tagged with one ticker, newest first. sentiment narrows to
    positive | negative | neutral."""
    return _guard(lambda: _compact(client().news(ticker.upper(), date=date, sentiment=sentiment, limit=max(1, min(limit, 50)))))


@mcp.tool()
def article(article_id: int) -> str:
    """One article by id, including its summary text."""
    return _guard(lambda: json.dumps(client().article(article_id), ensure_ascii=False))


@mcp.tool()
def trading_halts(ticker: Optional[str] = None, date: str = "today", limit: int = 25) -> str:
    """Nasdaq trading halts and resumptions with reason codes (T1 news pending,
    T2 news released, LUDP volatility, H10 SEC suspension…), ~20s after the
    exchange posts them."""
    return _guard(lambda: _compact(client().halts(ticker, date=date, limit=max(1, min(limit, 100)))))


@mcp.tool()
def sec_filings(ticker: Optional[str] = None, form: Optional[str] = None, date: str = "last7days", limit: int = 25) -> str:
    """SEC EDGAR filings as news. form: 8-K (material events) | 4 (insider
    trades) | S-1 (IPOs) | SC 13D (activist stakes) | 10-Q."""
    return _guard(lambda: _compact(client().filings(ticker, form=form, date=date, limit=max(1, min(limit, 100)))))


@mcp.tool()
def regulatory_actions(query: Optional[str] = None, date: str = "last7days", limit: int = 25) -> str:
    """FDA approvals and recalls, SEC and FTC actions, CFTC and UK FCA notices —
    the regulator feeds. query narrows by keyword (e.g. a drug or company)."""
    return _guard(lambda: _compact(client().news(category="regulatory", search=query, date=date, limit=max(1, min(limit, 100)))))


@mcp.tool()
def central_bank_news(source: Optional[str] = None, date: str = "last7days", limit: int = 25) -> str:
    """Central-bank and economy news. source: Federal Reserve | European Central
    Bank | Bank of England | Bank of Japan | Bank of Canada | Reserve Bank of
    Australia | Reserve Bank of India | CFTC, or any macro outlet."""
    return _guard(lambda: _compact(client().macro(source=source, date=date, limit=max(1, min(limit, 100)))))


@mcp.tool()
def market_sentiment(ticker: Optional[str] = None, date: str = "last7days") -> str:
    """Daily positive / negative / neutral article counts and average score for
    one ticker, or the whole market when ticker is omitted."""
    return _guard(lambda: json.dumps(client().sentiment(ticker, date)))


@mcp.tool()
def top_mentioned(date: str = "today", limit: int = 20) -> str:
    """Most-mentioned tickers across the whole feed over a preset window — an
    attention ranking."""
    return _guard(lambda: json.dumps(client().top_mentioned(date, max(1, min(limit, 100)))))


@mcp.tool()
def earnings_calendar(ticker: Optional[str] = None, days: int = 14) -> str:
    """Upcoming earnings dates (up to 60 days), with EPS estimates when known."""
    return _guard(lambda: json.dumps(client().earnings_calendar(ticker, max(1, min(days, 60)))))


@mcp.tool()
def analyst_ratings(ticker: str) -> str:
    """Analyst buy / hold / sell recommendation trends by month."""
    return _guard(lambda: json.dumps(client().ratings(ticker.upper())))


@mcp.tool()
def sundown_digest(refresh: bool = False) -> str:
    """End-of-day market recap. Served from a daily cache; generating a fresh
    one needs ANTHROPIC_API_KEY in this server's environment."""
    return _guard(lambda: json.dumps(client().sundown_digest(refresh=refresh), ensure_ascii=False))


@mcp.tool()
def list_sources(active_only: bool = True) -> str:
    """Source names with article counts — use the exact names with the
    `source` argument of search_news."""
    return _guard(lambda: json.dumps(client().sources(active_only)))


@mcp.tool()
def lookup_ticker(search: str, limit: int = 10) -> str:
    """Find symbols by ticker or company-name prefix in the SEC universe."""
    return _guard(lambda: json.dumps(client().tickers(search, max(1, min(limit, 50)))))


@mcp.tool()
def usage() -> str:
    """This key's plan, monthly quota and calls used. Not counted against quota."""
    return _guard(lambda: json.dumps(client().usage()))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
