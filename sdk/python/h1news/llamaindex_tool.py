"""LlamaIndex ToolSpec over the H1 News API.

    pip install "h1news[llamaindex]"

    from llama_index.core.agent.workflow import FunctionAgent
    from llama_index.llms.openai import OpenAI
    from h1news.llamaindex_tool import H1NewsToolSpec

    agent = FunctionAgent(tools=H1NewsToolSpec("sk_...").to_tool_list(), llm=OpenAI("gpt-4o-mini"))
    await agent.run("Summarise today's negative headlines on AAPL and TSLA.")
"""
from __future__ import annotations

import json
from typing import Optional

from llama_index.core.tools.tool_spec.base import BaseToolSpec

from h1news.client import H1News


class H1NewsToolSpec(BaseToolSpec):
    spec_functions = [
        "search_financial_news", "trading_halts", "sec_filings",
        "market_sentiment", "top_mentioned_tickers", "earnings_calendar", "analyst_ratings",
    ]

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self.client = H1News(api_key, **({"base_url": base_url} if base_url else {}))

    @staticmethod
    def _compact(articles: list[dict]) -> str:
        return json.dumps([
            {"id": a["id"], "title": a["title"], "source": a["source"], "published_at": a["published_at"],
             "tickers": a.get("tickers", []), "sentiment": a.get("sentiment", {}).get("label"),
             "category": a.get("category"), "url": a["url"]}
            for a in articles
        ], ensure_ascii=False)

    def search_financial_news(self, query: Optional[str] = None, ticker: Optional[str] = None,
                              category: Optional[str] = None, sentiment: Optional[str] = None,
                              date: str = "last7days", limit: int = 10) -> str:
        """Search ticker-tagged, sentiment-scored financial news. query: full-text
        (AND/OR). ticker: symbol. category: markets|earnings|macro|world|commodities|
        forex|crypto|halts|filings|regulatory. sentiment: positive|negative|neutral.
        date: today|yesterday|last7days|last30days."""
        page = self.client.news(ticker, search=query, category=category, sentiment=sentiment,
                                date=date, limit=min(limit, 50))
        return self._compact(page["results"])

    def trading_halts(self, ticker: Optional[str] = None, date: str = "today") -> str:
        """Nasdaq trading halts and resumptions with reason codes."""
        return self._compact(self.client.halts(ticker, date=date, limit=50)["results"])

    def sec_filings(self, ticker: Optional[str] = None, form: Optional[str] = None, date: str = "last7days") -> str:
        """SEC EDGAR filings as news. form: 8-K | 4 | S-1 | SC 13D | 10-Q."""
        return self._compact(self.client.filings(ticker, form=form, date=date, limit=50)["results"])

    def market_sentiment(self, ticker: Optional[str] = None, date: str = "last7days") -> str:
        """Daily positive/negative/neutral counts for a ticker or the whole market."""
        return json.dumps(self.client.sentiment(ticker, date))

    def top_mentioned_tickers(self, date: str = "today", limit: int = 20) -> str:
        """Most-mentioned tickers over a preset window."""
        return json.dumps(self.client.top_mentioned(date, limit))

    def earnings_calendar(self, ticker: Optional[str] = None, days: int = 14) -> str:
        """Upcoming earnings dates, up to 60 days out."""
        return json.dumps(self.client.earnings_calendar(ticker, days))

    def analyst_ratings(self, ticker: str) -> str:
        """Analyst buy/hold/sell recommendation trends."""
        return json.dumps(self.client.ratings(ticker))
