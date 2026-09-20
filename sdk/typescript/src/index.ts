/**
 * H1 News API client — Node 18+ and browsers (via stream tokens).
 *
 *   import { H1News } from "@heliusone/h1news";
 *   const news = new H1News({ apiKey: "sk_..." });
 *   const { results } = await news.news({ ticker: "AAPL", sentiment: "negative", date: "today" });
 *
 *   // Live stream (Pro) — reconnects and backfills gaps
 *   const stop = news.stream({ tickers: ["AAPL", "TSLA"], categories: ["earnings", "halts"] }, {
 *     onArticle: (a) => console.log(a.sentiment.label, a.title),
 *   });
 *
 * Every method returns the API's JSON unchanged; https://api.heliusone.com/docs
 * is the reference for shapes.
 */

export const VERSION = "0.1.0";
export const DEFAULT_BASE_URL = "https://api.heliusone.com";

// ── types ─────────────────────────────────────────────────────────────────────

export type Sentiment = "positive" | "negative" | "neutral";
export type ArticleType = "article" | "press_release" | "filing" | "social";
export type Category =
  | "markets" | "earnings" | "macro" | "world" | "commodities" | "forex"
  | "crypto" | "halts" | "filings" | "regulatory" | "general";
export type Region =
  | "us" | "uk" | "eu" | "jp" | "br" | "mx" | "latam" | "ca" | "au" | "in" | "cn" | "asia" | "global";
export type DatePreset =
  | "today" | "yesterday" | "last7days" | "last30days" | "yeartodate" | (string & {});

export interface Article {
  id: number;
  title: string;
  summary: string;
  url: string;
  source: string;
  type: ArticleType;
  category: Category;
  language: string;
  region: Region;
  tickers: string[];
  sentiment: { label: Sentiment; score: number };
  published_at: string;
  ingested_at: string;
}

export interface NewsPage {
  total: number;
  page: number;
  pages: number;
  results: Article[];
}

type ListOr<T> = T | T[];

export interface NewsParams {
  ticker?: ListOr<string>;
  match?: "any" | "all";
  collection?: string;
  source?: ListOr<string>;
  exclude_source?: ListOr<string>;
  type?: ArticleType;
  category?: ListOr<Category>;
  exclude_category?: ListOr<Category>;
  language?: ListOr<string>;
  region?: ListOr<Region>;
  sentiment?: Sentiment;
  search?: string;
  date?: DatePreset;
  since?: Date | string;
  until?: Date | string;
  since_id?: number;
  sort?: "newest" | "oldest";
  news_id?: ListOr<number>;
  fallback?: boolean;
  limit?: number;
  offset?: number;
}

export interface StreamFilters {
  tickers?: string[];
  sources?: string[];
  exclude_sources?: string[];
  types?: ArticleType[];
  exclude_types?: ArticleType[];
  categories?: Category[];
  exclude_categories?: Category[];
  languages?: string[];
  regions?: Region[];
}

export interface StreamHandlers {
  onArticle: (article: Article) => void;
  /** Connection-level events; the stream keeps going unless `fatal` is true. */
  onError?: (err: Error, fatal: boolean) => void;
  onOpen?: () => void;
  onClose?: (code: number, reason: string) => void;
}

export interface StreamOptions {
  /** Replay the gap through /v1/news?since_id= after a reconnect (default true). */
  backfill?: boolean;
  /** App-level ping cadence in ms (default 30000). */
  pingIntervalMs?: number;
  maxBackoffMs?: number;
  /** A WebSocket implementation when the runtime has no global one (Node < 22: `import WebSocket from "ws"`). */
  WebSocket?: typeof WebSocket;
}

export interface StreamToken { token: string; expires_in: number; ws_url: string }

// ── errors ────────────────────────────────────────────────────────────────────

export class H1NewsError extends Error {
  constructor(public status: number, public detail: string) {
    super(`HTTP ${status}: ${detail}`);
    this.name = "H1NewsError";
  }
}
/** 401 — missing or invalid key. */
export class AuthError extends H1NewsError { name = "AuthError"; }
/** 403 — the request needs a higher plan (multi-ticker, deep history, paging cap, the stream). */
export class PlanLimitError extends H1NewsError { name = "PlanLimitError"; }
/** 429 — per-minute rate limit or monthly quota. */
export class RateLimitError extends H1NewsError {
  name = "RateLimitError";
  constructor(status: number, detail: string, public retryAfter: number | null) { super(status, detail); }
}

// ── encoding ──────────────────────────────────────────────────────────────────

function encode(params: object): URLSearchParams {
  const out = new URLSearchParams();
  for (const [k, v] of Object.entries(params as Record<string, unknown>)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) { if (v.length) out.set(k, v.join(",")); }
    else if (v instanceof Date) out.set(k, v.toISOString());
    else if (typeof v === "boolean") out.set(k, v ? "true" : "false");
    else out.set(k, String(v));
  }
  return out;
}

async function raiseFor(resp: Response): Promise<void> {
  if (resp.ok) return;
  let detail: string = resp.statusText;
  try {
    const body = await resp.json();
    detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
  } catch { /* non-JSON body */ }
  if (resp.status === 401) throw new AuthError(401, detail);
  if (resp.status === 403) throw new PlanLimitError(403, detail);
  if (resp.status === 429) {
    const ra = resp.headers.get("Retry-After");
    throw new RateLimitError(429, detail, ra ? Number(ra) : null);
  }
  throw new H1NewsError(resp.status, detail);
}

// ── client ────────────────────────────────────────────────────────────────────

export interface H1NewsOptions {
  apiKey: string;
  baseUrl?: string;
  /** Your Anthropic key for generating the Sundown Digest (used once per generation, never stored). */
  anthropicKey?: string;
  fetch?: typeof fetch;
  /** Retries on 429 before throwing (default 2). */
  maxRetries?: number;
}

export class H1News {
  readonly apiKey: string;
  readonly baseUrl: string;
  private readonly anthropicKey?: string;
  private readonly fetchImpl: typeof fetch;
  private readonly maxRetries: number;

  constructor(opts: H1NewsOptions) {
    if (!opts?.apiKey) throw new Error("apiKey is required — get one at https://heliusone.com/newsapi");
    this.apiKey = opts.apiKey;
    this.baseUrl = (opts.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.anthropicKey = opts.anthropicKey;
    this.fetchImpl = opts.fetch ?? globalThis.fetch;
    this.maxRetries = opts.maxRetries ?? 2;
  }

  private async get<T>(path: string, params: object = {}, headers: Record<string, string> = {}): Promise<T> {
    const qs = encode(params).toString();
    const url = `${this.baseUrl}${path}${qs ? `?${qs}` : ""}`;
    for (let attempt = 0; ; attempt++) {
      const resp = await this.fetchImpl(url, {
        headers: { "X-API-Key": this.apiKey, "User-Agent": `h1news-ts/${VERSION}`, ...headers },
      });
      if (resp.status === 429 && attempt < this.maxRetries) {
        const ra = resp.headers.get("Retry-After");
        const delay = ra ? Number(ra) * 1000 : Math.min(2 ** attempt, 30) * 1000 + Math.random() * 1000;
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      await raiseFor(resp);
      return (await resp.json()) as T;
    }
  }

  /** GET /v1/news — history with every filter. */
  news(params: NewsParams = {}): Promise<NewsPage> { return this.get("/v1/news", params); }
  /** GET /v1/news/general — market news not tied to any ticker. */
  general(params: Omit<NewsParams, "ticker" | "match" | "collection"> = {}): Promise<NewsPage> { return this.get("/v1/news/general", params); }
  /** GET /v1/news/earnings */
  earnings(params: NewsParams = {}): Promise<NewsPage> { return this.get("/v1/news/earnings", params); }
  /** GET /v1/news/halts — Nasdaq trading halts / resumptions. */
  halts(params: NewsParams = {}): Promise<NewsPage> { return this.get("/v1/news/halts", params); }
  /** GET /v1/news/filings — SEC EDGAR; form = 8-K | 4 | S-1 | SC 13D | 10-Q. */
  filings(params: NewsParams & { form?: string } = {}): Promise<NewsPage> { return this.get("/v1/news/filings", params); }
  /** GET /v1/news/macro — central banks & economy. */
  macro(params: NewsParams = {}): Promise<NewsPage> { return this.get("/v1/news/macro", params); }
  /** GET /v1/news/category/{category} */
  category(name: Category, params: NewsParams = {}): Promise<NewsPage> { return this.get(`/v1/news/category/${name}`, params); }
  /** GET /v1/news/{id} */
  article(id: number): Promise<Article> { return this.get(`/v1/news/${id}`); }
  /** GET /v1/usage — plan, quota, usage (not metered). */
  usage(): Promise<{ month: string; plan: string; monthly_quota: number | null; used_this_month: number; remaining: number | null; rate_limit_per_min: number }> { return this.get("/v1/usage"); }
  /** GET /v1/tickers — SEC symbol universe; `search` is a prefix. */
  tickers(params: { search?: string; limit?: number } = {}) { return this.get<{ count: number; results: { symbol: string; name: string }[] }>("/v1/tickers", params); }
  /** GET /v1/sources */
  sources(params: { active_only?: boolean } = {}) { return this.get<{ count: number; results: { source: string; count: number; active: boolean }[] }>("/v1/sources", params); }
  /** GET /v1/categories */
  categories() { return this.get<{ count: number; results: { category: string; count: number }[] }>("/v1/categories"); }
  /** GET /v1/top-mentioned */
  topMentioned(params: { date?: DatePreset; limit?: number } = {}) { return this.get<{ window: string; count: number; results: { ticker: string; mentions: number }[] }>("/v1/top-mentioned", params); }
  /** GET /v1/sentiment — daily breakdown for a ticker or the market. */
  sentiment(params: { ticker?: string; date?: DatePreset } = {}) { return this.get<{ ticker: string | null; window: string; daily: { date: string; total: number; positive: number; negative: number; neutral: number; avg_score: number }[] }>("/v1/sentiment", params); }
  /** GET /v1/earnings-calendar */
  earningsCalendar(params: { ticker?: string; days?: number } = {}) { return this.get<{ from: string; days: number; count: number; results: Record<string, unknown>[] }>("/v1/earnings-calendar", params); }
  /** GET /v1/ratings */
  ratings(ticker: string) { return this.get<Record<string, unknown>>("/v1/ratings", { ticker }); }
  /** GET /v1/sundown-digest — cached daily; generating needs your Anthropic key. */
  sundownDigest(opts: { refresh?: boolean; anthropicKey?: string } = {}) {
    const key = opts.anthropicKey ?? this.anthropicKey;
    return this.get<Record<string, unknown>>("/v1/sundown-digest", { refresh: opts.refresh || undefined }, key ? { "X-Anthropic-Key": key } : {});
  }

  /** POST /v1/stream/token — hand the token to a browser; the key stays on your server. Pro plan. */
  async streamToken(): Promise<StreamToken> {
    const resp = await this.fetchImpl(`${this.baseUrl}/v1/stream/token`, {
      method: "POST", headers: { "X-API-Key": this.apiKey, "User-Agent": `h1news-ts/${VERSION}` },
    });
    await raiseFor(resp);
    return (await resp.json()) as StreamToken;
  }

  /** Walk /v1/news page by page. Stops at `maxItems`, the end, or the plan's paging cap (throws PlanLimitError). */
  async *iterNews(params: NewsParams = {}, opts: { pageSize?: number; maxItems?: number } = {}): AsyncGenerator<Article> {
    const pageSize = opts.pageSize ?? 200;
    let offset = 0, n = 0;
    for (;;) {
      const page = await this.news({ ...params, limit: pageSize, offset });
      for (const a of page.results) {
        yield a;
        if (opts.maxItems !== undefined && ++n >= opts.maxItems) return;
      }
      if (page.results.length < pageSize) return;
      offset += pageSize;
    }
  }

  /**
   * Live stream (Pro). Returns a `stop()` function. Reconnects with backoff on
   * drops and replays the gap through /v1/news?since_id= so delivery is gapless.
   * Auth and plan rejections are fatal (`onError(err, true)`) and stop the stream.
   */
  stream(filters: StreamFilters, handlers: StreamHandlers, opts: StreamOptions = {}): () => void {
    return openStream({ api_key: this.apiKey }, this.baseUrl, filters, handlers, {
      ...opts,
      backfillFetch: opts.backfill === false ? undefined : (sinceId) => this.news({
        ticker: filters.tickers, source: filters.sources, exclude_source: filters.exclude_sources,
        category: filters.categories, exclude_category: filters.exclude_categories,
        language: filters.languages, region: filters.regions,
        since_id: sinceId, sort: "oldest", limit: 200,
      }),
    });
  }
}

// ── stream (shared by key-auth and token-auth) ────────────────────────────────

/**
 * Browser-side stream with a token from `POST /v1/stream/token` (minted on your
 * server). No API key is involved on the client; backfill is off because the
 * token cannot call REST — mint a fresh token before each reconnect via
 * `refreshToken` if you want the stream to outlive one token's lifetime.
 */
export function streamWithToken(
  token: string,
  filters: StreamFilters,
  handlers: StreamHandlers,
  opts: StreamOptions & { wsUrl?: string; refreshToken?: () => Promise<string> } = {},
): () => void {
  const wsBase = (opts.wsUrl ?? `${DEFAULT_BASE_URL}/v1/stream`).replace(/\/v1\/stream$/, "");
  return openStream({ token }, wsBase, filters, handlers, { ...opts, refreshToken: opts.refreshToken });
}

function wsUrl(base: string, auth: Record<string, string>, filters: StreamFilters): string {
  const ws = base.replace(/^https:\/\//, "wss://").replace(/^http:\/\//, "ws://");
  const qs = encode({ ...auth, ...filters }).toString();
  return `${ws}/v1/stream?${qs}`;
}

function openStream(
  auth: Record<string, string>,
  base: string,
  filters: StreamFilters,
  handlers: StreamHandlers,
  opts: StreamOptions & { backfillFetch?: (sinceId: number) => Promise<NewsPage>; refreshToken?: () => Promise<string> },
): () => void {
  const WS = opts.WebSocket ?? (globalThis as any).WebSocket as typeof WebSocket | undefined;
  if (!WS) throw new Error("No WebSocket implementation: pass opts.WebSocket (e.g. from the 'ws' package) on Node < 22");
  const pingMs = opts.pingIntervalMs ?? 30_000;
  const maxBackoff = opts.maxBackoffMs ?? 30_000;
  let backoff = 1_000;
  let lastId: number | null = null;
  let stopped = false;
  let socket: WebSocket | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const fail = (err: Error, fatal: boolean) => { handlers.onError?.(err, fatal); if (fatal) stop(); };

  const connect = async () => {
    if (stopped) return;
    let currentAuth = auth;
    if (opts.refreshToken && "token" in auth && lastId !== null) {
      try { currentAuth = { token: await opts.refreshToken() }; } catch (e) { fail(e as Error, false); }
    }
    const ws = new WS(wsUrl(base, currentAuth, filters));
    socket = ws;
    ws.onopen = async () => {
      backoff = 1_000;
      handlers.onOpen?.();
      if (opts.backfillFetch && lastId !== null) {
        try {
          const page = await opts.backfillFetch(lastId);
          for (const a of page.results) { lastId = Math.max(lastId ?? 0, a.id); handlers.onArticle(a); }
        } catch (e) { fail(e as Error, false); }
      }
      pingTimer = setInterval(() => { if (ws.readyState === ws.OPEN) ws.send(JSON.stringify({ action: "ping" })); }, pingMs);
    };
    ws.onmessage = (ev: MessageEvent) => {
      let msg: any;
      try { msg = JSON.parse(String(ev.data)); } catch { return; }
      if (!msg || typeof msg !== "object") return;
      if ("pong" in msg || "ack" in msg) return;
      if ("error" in msg) {
        const fatal = msg.code === "plan_upgrade_required";
        fail(fatal ? new PlanLimitError(403, msg.error) : new H1NewsError(0, String(msg.error)), fatal);
        return;
      }
      if (typeof msg.id === "number") lastId = Math.max(lastId ?? 0, msg.id);
      handlers.onArticle(msg as Article);
    };
    ws.onclose = (ev: CloseEvent) => {
      if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
      handlers.onClose?.(ev.code, ev.reason);
      if (stopped) return;
      if (ev.code === 1008) return fail(new AuthError(401, "invalid API key or token"), true);
      if (ev.code === 4403) return fail(new PlanLimitError(403, "the live stream is a Pro-plan feature"), true);
      reconnectTimer = setTimeout(connect, backoff + Math.random() * 500);
      backoff = Math.min(backoff * 2, maxBackoff);
    };
    ws.onerror = () => { /* onclose follows with the code */ };
  };

  const stop = () => {
    stopped = true;
    if (pingTimer) clearInterval(pingTimer);
    if (reconnectTimer) clearTimeout(reconnectTimer);
    try { socket?.close(1000, "client stop"); } catch { /* already closed */ }
  };

  void connect();
  return stop;
}
