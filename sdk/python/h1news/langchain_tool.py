"""LangChain tools over the H1 News API.

    pip install "h1news[langchain]"

    from langchain_openai import ChatOpenAI          # or any chat model
    from langgraph.prebuilt import create_react_agent
    from h1news.langchain_tool import h1news_tools

    agent = create_react_agent(ChatOpenAI(model="gpt-4o-mini"), h1news_tools("sk_..."))
    agent.invoke({"messages": [("user", "Any negative news on NVDA today? Anything halted?")]})

Each tool returns a compact JSON string (title, source, time, tickers,
sentiment, url) so a model can read a page of results in a few hundred tokens.
"""
from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import tool

from h1news.client import H1News


def _compact(articles: list[dict]) -> str:
    return json.dumps([
        {
            "id": a["id"], "title": a["title"], "source": a["source"],
            "published_at": a["published_at"], "tickers": a.get("tickers", []),
            "sentiment": a.get("sentiment", {}).get("label"),
            "category": a.get("category"), "url": a["url"],
        }
        for a in articles
    ], ensure_ascii=False)


def h1news_tools(api_key: str, *, base_url: str | None = None) -> list:
    """Build the tool set bound to one API key."""
    client = H1News(api_key, **({"base_url": base_url} if base_url else {}))

    @tool
    def search_financial_news(
        query: Optional[str] = None,
        ticker: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        date: str = "last7days",
        limit: int = 10,
    ) -> str:
        """Search ticker-tagged, sentiment-scored financial news. `query` is
        full-text (supports AND / OR); `ticker` is a symbol like NVDA;
        `category` is one of markets, earnings, macro, world, commodities,
        forex, crypto, halts, filings, regulatory; `sentiment` is positive |
        negative | neutral; `date` is today | yesterday | last7days | last30days."""
        page = client.news(ticker, search=query, category=category, sentiment=sentiment,
                           date=date, limit=min(limit, 50))
        return _compact(page["results"])

    @tool
    def trading_halts(ticker: Optional[str] = None, date: str = "today") -> str:
        """Nasdaq trading halts and resumptions, with reason codes, for a
        ticker or the whole market."""
        return _compact(client.halts(ticker, date=date, limit=50)["results"])

    @tool
    def sec_filings(ticker: Optional[str] = None, form: Optional[str] = None, date: str = "last7days") -> str:
        """SEC EDGAR filings as news. `form` is 8-K | 4 | S-1 | SC 13D | 10-Q."""
        return _compact(client.filings(ticker, form=form, date=date, limit=50)["results"])

    @tool
    def market_sentiment(ticker: Optional[str] = None, date: str = "last7days") -> str:
        """Daily positive / negative / neutral article counts for a ticker, or
        the whole market when no ticker is given."""
        return json.dumps(client.sentiment(ticker, date))

    @tool
    def top_mentioned_tickers(date: str = "today", limit: int = 20) -> str:
        """Most-mentioned tickers across the feed over a preset window — a live
        attention ranking."""
        return json.dumps(client.top_mentioned(date, limit))

    @tool
    def earnings_calendar(ticker: Optional[str] = None, days: int = 14) -> str:
        """Upcoming earnings dates, up to 60 days out."""
        return json.dumps(client.earnings_calendar(ticker, days))

    @tool
    def analyst_ratings(ticker: str) -> str:
        """Analyst buy / hold / sell recommendation trends for a ticker."""
        return json.dumps(client.ratings(ticker))

    return [
        search_financial_news, trading_halts, sec_filings, market_sentiment,
        top_mentioned_tickers, earnings_calendar, analyst_ratings,
    ]
