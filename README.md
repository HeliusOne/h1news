# H1 News API — SDKs, MCP server & examples

[H1 News API](https://heliusone.com/newsapi) is real-time financial news from 135+ sources — every article tagged with its tickers, scored for sentiment, categorized, and pushed over a WebSocket the moment it is ingested. This repo holds everything a developer needs on the client side. The service itself runs hosted at `https://api.heliusone.com`; the interactive reference is at [api.heliusone.com/docs](https://api.heliusone.com/docs).

Get a key: [heliusone.com/newsapi](https://heliusone.com/newsapi) — Basic $19.99/mo, Pro $49.99/mo, 5-day free trial on both. Status: [heliusone.com/newsapi/status](https://heliusone.com/newsapi/status).

| | |
|---|---|
| [`sdk/python`](sdk/python) | **`h1news`** — sync + async clients, a `stream()` that reconnects and backfills gaps, typed errors, LangChain tools and a LlamaIndex ToolSpec |
| [`sdk/typescript`](sdk/typescript) | **`@heliusone/h1news`** — Node 18+ and browsers; `stream()` server-side, `streamWithToken()` in the browser |
| [`sdk/mcp`](sdk/mcp) | **`h1news-mcp`** — 15 tools for Claude Desktop, Claude Code, Cursor and any MCP client |
| [`examples/`](examples) | Halt sniper, sentiment dashboard (Streamlit), daily digest email, a resilient WebSocket client, a Postman collection |
| [`examples/integrations`](examples/integrations) | n8n workflow, Make and Zapier recipes, an Alpaca paper-trading strategy, an OpenBB provider extension |
| [Guides](https://heliusone.com/newsapi/guides) | Runnable walkthroughs: WebSocket streaming in Python, FDA approvals, trading halts, international markets, AI agents |

## Quick start

```bash
pip install h1news                         # or: pip install "git+https://github.com/HeliusOne/h1news.git#subdirectory=sdk/python"
```

```python
from h1news import H1News
news = H1News("sk_...")
for a in news.news("NVDA", sentiment="negative", date="today")["results"]:
    print(a["published_at"], a["source"], a["title"])
```

```bash
curl -H 'X-API-Key: sk_...' 'https://api.heliusone.com/v1/news/halts?date=today'
```

## Contributing

Issues and pull requests are welcome here — the SDKs, server and examples are MIT licensed. Questions about the API itself (sources, plans, data quality) go to [support@heliusone.com](mailto:support@heliusone.com). Releases are cut by tag; see [`sdk/RELEASING.md`](sdk/RELEASING.md).
