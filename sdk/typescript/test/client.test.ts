import { test } from "node:test";
import assert from "node:assert/strict";
import { H1News, AuthError, PlanLimitError, RateLimitError } from "../src/index.js";

function fakeFetch(handler: (url: string, init?: RequestInit) => Response): typeof fetch {
  return (async (input: any, init?: RequestInit) => handler(String(input), init)) as typeof fetch;
}
const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

test("news() encodes lists, dates and booleans the way the API expects", async () => {
  let seen = "";
  const c = new H1News({ apiKey: "k", fetch: fakeFetch((url, init) => {
    seen = url;
    assert.equal((init!.headers as Record<string, string>)["X-API-Key"], "k");
    return json(200, { total: 0, results: [] });
  }) });
  await c.news({ ticker: ["AAPL", "TSLA"], category: ["earnings", "halts"], since: new Date("2026-09-01T00:00:00Z"), fallback: true, limit: 5 });
  const u = new URL(seen);
  assert.equal(u.pathname, "/v1/news");
  assert.equal(u.searchParams.get("ticker"), "AAPL,TSLA");
  assert.equal(u.searchParams.get("category"), "earnings,halts");
  assert.equal(u.searchParams.get("since"), "2026-09-01T00:00:00.000Z");
  assert.equal(u.searchParams.get("fallback"), "true");
});

test("status codes map to typed errors", async () => {
  for (const [status, Err] of [[401, AuthError], [403, PlanLimitError], [429, RateLimitError]] as const) {
    const c = new H1News({ apiKey: "k", maxRetries: 0, fetch: fakeFetch(() => json(status, { detail: "nope" }, { "Retry-After": "3" })) });
    await assert.rejects(c.usage(), (e: any) => e instanceof Err && e.status === status && e.detail === "nope");
  }
});

test("a 429 is retried then succeeds", async () => {
  let n = 0;
  const c = new H1News({ apiKey: "k", fetch: fakeFetch(() => (++n === 1 ? json(429, { detail: "slow" }, { "Retry-After": "0" }) : json(200, { ok: true }))) });
  assert.deepEqual(await c.usage(), { ok: true });
  assert.equal(n, 2);
});

test("iterNews pages until a short page", async () => {
  const pages: Record<string, number[]> = { "0": [0, 1, 2], "3": [3] };
  const c = new H1News({ apiKey: "k", fetch: fakeFetch((url) => {
    const off = new URL(url).searchParams.get("offset") ?? "0";
    return json(200, { results: (pages[off] ?? []).map((id) => ({ id })) });
  }) });
  const ids: number[] = [];
  for await (const a of c.iterNews({ ticker: "AAPL" }, { pageSize: 3 })) ids.push(a.id);
  assert.deepEqual(ids, [0, 1, 2, 3]);
});

test("sundownDigest sends the Anthropic key only when given", async () => {
  const seen: (string | undefined)[] = [];
  const c = new H1News({ apiKey: "k", fetch: fakeFetch((_u, init) => { seen.push((init!.headers as any)["X-Anthropic-Key"]); return json(200, {}); }) });
  await c.sundownDigest();
  await c.sundownDigest({ anthropicKey: "ak" });
  assert.deepEqual(seen, [undefined, "ak"]);
});
