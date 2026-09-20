"""Resilient WebSocket client for the live feed.

A single WebSocket can't stay up forever (redeploys, network blips, and on Cloud
Run a hard 60-min request cap all drop it). So this client treats a drop as a
non-event: it auto-reconnects with backoff and, on every reconnect, backfills the
gap via REST (`/v1/news?since_id=...`) so no article is missed. The feed you see
is continuous even though the underlying connection cycles.

    pip install websockets
    python examples/ws_client.py --key demo-key                # all news
    python examples/ws_client.py --key demo-key AAPL TSLA      # filter by ticker
    python examples/ws_client.py --key sk_... --url wss://api.heliusone.com/v1/stream AAPL
"""
import argparse
import asyncio
import json
import urllib.parse
import urllib.request

import websockets

PING_INTERVAL = 30  # app-level keepalive, seconds


def _rest_base(ws_url: str) -> str:
    """Derive the REST /v1/news endpoint from the ws:// stream URL."""
    base = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    return base.rsplit("/v1/stream", 1)[0] + "/v1/news"


def _render(article: dict) -> None:
    s = article.get("sentiment", {})
    print(
        f"#{article.get('id','?'):<7} "
        f"[{s.get('label','?'):8}] "
        f"{','.join(article.get('tickers', [])) or '-':14} "
        f"{article.get('source','')} :: {article.get('title','')}"
    )


async def _backfill(rest_url: str, api_key: str, tickers: list[str], since_id: int) -> int:
    """Replay everything stored since `since_id` (oldest-first). Returns new max id."""
    params = {"api_key": api_key, "since_id": since_id, "sort": "oldest", "limit": 200}
    if tickers:
        params["ticker"] = ",".join(tickers)
    url = f"{rest_url}?{urllib.parse.urlencode(params)}"

    def _fetch() -> dict:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())

    data = await asyncio.to_thread(_fetch)
    last = since_id
    for article in data.get("results", []):
        _render(article)
        last = max(last, article.get("id", last))
    return last


async def _keepalive(ws) -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL)
        await ws.send(json.dumps({"action": "ping"}))


async def run(api_key: str, tickers: list[str], ws_base: str) -> None:
    rest_url = _rest_base(ws_base)
    url = f"{ws_base}?api_key={api_key}"
    if tickers:
        url += "&tickers=" + ",".join(tickers)

    last_id = 0          # highest article id we've delivered to the user
    backoff = 1.0        # reconnect backoff, capped at 30s

    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                # New connection established: close the gap before going live.
                if last_id:
                    last_id = await _backfill(rest_url, api_key, tickers, last_id)
                print(f"connected (filter: {tickers or 'all'}, resuming after id {last_id})")
                backoff = 1.0

                pinger = asyncio.create_task(_keepalive(ws))
                try:
                    async for raw in ws:
                        msg = json.loads(raw)
                        if "pong" in msg or "ack" in msg:
                            continue  # control frame, not an article
                        _render(msg)
                        last_id = max(last_id, msg.get("id", last_id))
                finally:
                    pinger.cancel()
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            print(f"disconnected ({exc.__class__.__name__}: {exc}); reconnecting in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--key", default="demo-key", help="API key")
    p.add_argument("--url", default="ws://localhost:8000/v1/stream",
                   help="stream endpoint, e.g. wss://api.heliusone.com/v1/stream")
    p.add_argument("tickers", nargs="*", help="optional ticker filters")
    args = p.parse_args()
    try:
        asyncio.run(run(args.key, args.tickers, args.url))
    except KeyboardInterrupt:
        print("\nbye")
