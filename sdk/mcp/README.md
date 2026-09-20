# h1news-mcp — H1 News for Claude, Cursor and any MCP client

An [MCP](https://modelcontextprotocol.io) server that gives an AI assistant real-time, ticker-tagged, sentiment-scored financial news from 135+ sources: search, per-ticker news, trading halts, SEC filings, regulator actions, central-bank news, sentiment, top-mentioned tickers, the earnings calendar, analyst ratings and the Sundown Digest. Get a key at [heliusone.com/newsapi](https://heliusone.com/newsapi).

```bash
pip install h1news-mcp
```

## Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "h1news": {
      "command": "h1news-mcp",
      "env": { "H1NEWS_API_KEY": "sk_..." }
    }
  }
}
```

Restart Claude Desktop, then ask: *"Anything halted today? Any negative news on my NVDA position this week? What did the Fed say?"*

## Claude Code

```bash
claude mcp add h1news -e H1NEWS_API_KEY=sk_... -- h1news-mcp
```

## Cursor / Windsurf / other clients

Same shape — a stdio server started with the `h1news-mcp` command and `H1NEWS_API_KEY` in its environment. Use `uvx --from h1news-mcp h1news-mcp` if you prefer not to install into a global Python.

## Tools

| Tool | What it answers |
|---|---|
| `search_news` | Anything: full-text (AND / OR), ticker, category, sentiment, region, language, source, date window |
| `ticker_news` | Latest headlines for one symbol |
| `article` | One article with its summary text |
| `trading_halts` | Nasdaq halts / resumptions with reason codes |
| `sec_filings` | 8-K, Form 4, S-1, SC 13D, 10-Q as news |
| `regulatory_actions` | FDA, SEC, FTC, CFTC, FCA |
| `central_bank_news` | Fed, ECB, BoE, BoJ, BoC, RBA, RBI |
| `market_sentiment` | Daily positive / negative / neutral counts for a ticker or the market |
| `top_mentioned` | Attention ranking of tickers |
| `earnings_calendar`, `analyst_ratings` | Upcoming reports; buy / hold / sell trends |
| `sundown_digest` | End-of-day recap (set `ANTHROPIC_API_KEY` to generate a fresh one) |
| `list_sources`, `lookup_ticker`, `usage` | Reference and quota |

Results are compact JSON (title, source, time, tickers, sentiment, category, url) so a page of ten costs a few hundred tokens; the model can open `url` when it needs the full article.

## Environment

| Variable | Purpose |
|---|---|
| `H1NEWS_API_KEY` | required |
| `H1NEWS_BASE_URL` | default `https://api.heliusone.com` |
| `ANTHROPIC_API_KEY` | optional — only to generate the Sundown Digest on a cache miss |

Basic keys get one ticker per call and 30 days of history; Pro keys get multi-ticker queries and the full archive. Plan errors come back as `{"error": …}` so the assistant can say what to change.
