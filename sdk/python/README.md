# h1news — Python client for the H1 News API

Real-time, ticker-tagged, sentiment-scored financial news from 135+ sources over REST and WebSocket. Get a key at [heliusone.com/newsapi](https://heliusone.com/newsapi); the endpoint reference is at [api.heliusone.com/docs](https://api.heliusone.com/docs).

```bash
pip install h1news            # from PyPI once published; until then:
pip install "git+https://github.com/HeliusOne/h1news.git#subdirectory=sdk/python"
```

## REST

```python
from h1news import H1News

news = H1News("sk_...")

# Latest negative headlines on a ticker
for a in news.news("NVDA", sentiment="negative", date="today")["results"]:
    print(a["published_at"], a["source"], a["title"])

# Trading halts, SEC filings, central banks — same filters everywhere
news.halts(date="today")
news.filings("TSLA", form="8-K", date="last7days")
news.macro(source="Federal Reserve")
news.category("regulatory", date="last7days")          # FDA / SEC / FTC / FCA actions

# Multi-ticker (Pro), curated baskets, full-text search with AND / OR
news.news(["AAPL", "MSFT", "GOOGL"], match="any")
news.news(collection="MAG7", category="earnings")
news.news(search="guidance AND raise", date="last30days")

# Analytics
news.sentiment("TSLA", date="last7days")
news.top_mentioned(date="today", limit=10)
news.earnings_calendar(days=14)
news.ratings("NVDA")
news.sundown_digest(anthropic_key="sk-ant-...")        # cached daily; your key is used once

# Walk history page by page; poll for what's new without the stream
for a in news.iter_news("AAPL", date="last30days", max_items=1000): ...
for a in news.poll("AAPL", interval=30): print("new:", a["title"])
```

Errors are typed: `AuthError` (401), `PlanLimitError` (403 — multi-ticker, deep history, paging cap or the stream on Basic), `RateLimitError` (429, with `retry_after`), `H1NewsError` for the rest. A 429 is retried once automatically.

## Live stream (Pro)

```python
import asyncio
from h1news import AsyncH1News

async def main():
    async with AsyncH1News("sk_...") as news:
        async for a in news.stream(tickers=["AAPL", "TSLA"], categories=["earnings", "halts"]):
            print(a["sentiment"]["label"], a["title"])

asyncio.run(main())
```

`stream()` reconnects with backoff when the socket drops and replays the gap through `/v1/news?since_id=` before resuming, so what you iterate is gapless. One connection costs one API call; pushed articles are free.

**Browsers:** never ship your key to a page. Call `news.stream_token()` on your server and hand the page the returned token; it connects to `ws_url?token=…` directly (see the TypeScript SDK).

## AI agents

```python
from h1news.langchain_tool import h1news_tools          # pip install "h1news[langchain]"
from h1news.llamaindex_tool import H1NewsToolSpec       # pip install "h1news[llamaindex]"
```

Seven tools each — search, halts, filings, sentiment, top-mentioned, earnings calendar, ratings — returning compact JSON a model reads in a few hundred tokens. For Claude Desktop, Cursor or any MCP client, see [`sdk/mcp`](../mcp).

## Plans

| | Basic $19.99/mo | Pro $49.99/mo |
|---|---|---|
| Calls / month | 20,000 | 50,000 |
| Tickers per call | 1 | 25 |
| History | 30 days | full archive |
| WebSocket stream | — | included |

5-day free trial on both. Every REST endpoint is available on both tiers.
