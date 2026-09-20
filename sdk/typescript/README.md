# @heliusone/h1news — TypeScript client for the H1 News API

Real-time, ticker-tagged, sentiment-scored financial news from 135+ sources over REST and WebSocket. Node 18+ and browsers (via stream tokens). Get a key at [heliusone.com/newsapi](https://heliusone.com/newsapi); the endpoint reference is at [api.heliusone.com/docs](https://api.heliusone.com/docs).

```bash
npm install @heliusone/h1news
```

## REST

```ts
import { H1News } from "@heliusone/h1news";

const news = new H1News({ apiKey: process.env.H1NEWS_API_KEY! });

const { total, results } = await news.news({ ticker: "NVDA", sentiment: "negative", date: "today" });
await news.halts({ date: "today" });
await news.filings({ ticker: "TSLA", form: "8-K", date: "last7days" });
await news.category("regulatory", { date: "last7days" });        // FDA / SEC / FTC / FCA
await news.news({ collection: "MAG7", category: "earnings" });    // Pro: multi-ticker + baskets
await news.news({ search: "guidance AND raise", date: "last30days" });

await news.sentiment({ ticker: "TSLA", date: "last7days" });
await news.topMentioned({ date: "today", limit: 10 });
await news.earningsCalendar({ days: 14 });
await news.ratings("NVDA");

for await (const a of news.iterNews({ ticker: "AAPL", date: "last30days" }, { maxItems: 1000 })) { /* … */ }
```

Errors are typed: `AuthError` (401), `PlanLimitError` (403), `RateLimitError` (429, `retryAfter`), `H1NewsError`. A 429 is retried twice with backoff.

## Live stream (Pro) — server side

```ts
const stop = news.stream(
  { tickers: ["AAPL", "TSLA"], categories: ["earnings", "halts"] },
  {
    onArticle: (a) => console.log(a.sentiment.label, a.title),
    onError: (err, fatal) => console.error(fatal ? "stopped:" : "retrying:", err.message),
  },
);
// later: stop();
```

Reconnects with backoff when the socket drops and replays the gap through `/v1/news?since_id=` first, so delivery is gapless. Node < 22 has no global `WebSocket`: pass one — `news.stream(filters, handlers, { WebSocket: (await import("ws")).default })`.

## Live stream — in the browser, without exposing your key

```ts
// server (Next.js route, Express, a Cloud Function…)
app.post("/api/news-token", async (_req, res) => res.json(await news.streamToken()));

// browser
import { streamWithToken } from "@heliusone/h1news";
const { token, ws_url } = await (await fetch("/api/news-token", { method: "POST" })).json();
const stop = streamWithToken(token, { tickers: ["AAPL"] }, { onArticle: render }, {
  wsUrl: ws_url,
  refreshToken: async () => (await (await fetch("/api/news-token", { method: "POST" })).json()).token,
});
```

Tokens live a few minutes and are checked only at connect time; `refreshToken` is called before each reconnect.

## Plans

| | Basic $19.99/mo | Pro $49.99/mo |
|---|---|---|
| Calls / month | 20,000 | 50,000 |
| Tickers per call | 1 | 25 |
| History | 30 days | full archive |
| WebSocket stream | — | included |

5-day free trial on both. Every REST endpoint is available on both tiers.
