# Integrations

Ready-made ways to plug the H1 News API into tools you already run. Every recipe needs a key from [heliusone.com/newsapi](https://heliusone.com/newsapi); the endpoint reference is at [api.heliusone.com/docs](https://api.heliusone.com/docs).

| File | What it does |
|---|---|
| [`n8n-ticker-news-to-slack.json`](n8n-ticker-news-to-slack.json) | n8n workflow: every 5 minutes, new headlines for a watchlist → Slack, with sentiment and a per-ticker high-water mark so nothing repeats |
| [Make recipe](#make-formerly-integromat) | The same flow in Make, module by module |
| [`alpaca_news_strategy.py`](alpaca_news_strategy.py) | Alpaca paper-trading strategy that reacts to negative primary-source headlines on held positions (stream, Pro) |
| [`openbb_h1news/`](openbb_h1news/) | OpenBB Platform provider extension: `obb.news.company(symbol="NVDA", provider="h1news")` |
| [`../../sdk/python`](../../sdk/python) | LangChain tools and a LlamaIndex ToolSpec (`h1news.langchain_tool`, `h1news.llamaindex_tool`) |
| [`../../sdk/mcp`](../../sdk/mcp) | MCP server for Claude Desktop, Claude Code, Cursor |

## n8n

Import the JSON (Workflows → Import from file), then:

1. Create a **Header Auth** credential: name `X-API-Key`, value your key. Attach it to the *GET /v1/news* node.
2. Attach your Slack credential to the *Slack* node and pick the channel.
3. Optionally set the env var `H1NEWS_WATCHLIST=AAPL,TSLA,NVDA` on your n8n instance (defaults to those three).

Cost: one API call per ticker per run. Three tickers every 5 minutes ≈ 26k calls/month, so trim the interval or the list on Basic (20k/month), or use a Pro key and change the URL to `ticker=AAPL,TSLA,NVDA` in a single call (edit the *Watchlist* node to emit one item).

## Make (formerly Integromat)

Make blueprints embed account-specific ids, so build this one in the editor — five modules, five minutes:

1. **Schedule** — trigger: every 5 minutes.
2. **HTTP → Make a request** — URL `https://api.heliusone.com/v1/news?ticker=AAPL&date=today&limit=20`, method GET, header `X-API-Key: <your key>`, *Parse response*: yes.
3. **Iterator** — array: `2. Data → results[]`.
4. **Data store → Get a record** (key `3. id`) + a **Filter** on the route: *Record exists* = no. This is the dedupe; add **Data store → Add/replace a record** after the Slack step to write the id. (Alternative without a data store: keep the last id in a Make variable and add `&since_id={{lastId}}` to the URL.)
5. **Slack → Create a Message** — channel `#market-news`, text:
   ```
   {{if(3.sentiment.label = "negative"; "🔴"; if(3.sentiment.label = "positive"; "🟢"; "⚪"))}} *{{join(3.tickers; ", ")}}* — <{{3.url}}|{{3.title}}>
   _{{3.source}} · {{3.category}} · {{formatDate(3.published_at; "YYYY-MM-DD HH:mm")}} UTC_
   ```

Swap step 2's URL for `/v1/news/halts?date=today` and you have a halt alerter; for `/v1/news?category=regulatory&date=today` an FDA / SEC / FTC watcher.

## Zapier

Same shape as Make: *Schedule by Zapier* → *Webhooks by Zapier (GET)* with the `X-API-Key` header → *Looping by Zapier* over `results` → *Slack*. *Storage by Zapier* holding the last `id` plays the role of `since_id`.
