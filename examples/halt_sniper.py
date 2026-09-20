#!/usr/bin/env python3
"""Halt sniper — alert the moment a stock is halted, with the headlines behind it.

Streams Nasdaq trading halts (category=halts) over the WebSocket, and for each
halt pulls the last few headlines tagged with that symbol so the alert explains
*why* the name is halted (T1 "news pending" halts usually precede a release by
minutes). Posts to a Slack or Discord webhook when one is configured, and
always prints to stdout.

    pip install h1news
    export H1NEWS_API_KEY=sk_...                      # Pro plan (the stream)
    export ALERT_WEBHOOK_URL=https://hooks.slack.com/services/...   # optional
    python examples/halt_sniper.py                    # every halt
    python examples/halt_sniper.py --watch NVDA TSLA  # only your names

Halt reason codes (Nasdaq): T1 news pending · T2 news released · T12 additional
information requested · LUDP limit-up/limit-down pause · H10 SEC suspension ·
M pending regulatory · D1 delisting.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import urllib.request

from h1news import AsyncH1News

_REASON = re.compile(r"\b(T1|T2|T3|T5|T6|T8|T12|H4|H9|H10|H11|LUDP|MWC[123]|M|D1)\b")


def _post(webhook: str, text: str) -> None:
    body = json.dumps({"text": text, "content": text}).encode()   # Slack reads text, Discord reads content
    req = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


async def main(watch: set[str], webhook: str | None) -> None:
    key = os.environ.get("H1NEWS_API_KEY")
    if not key:
        raise SystemExit("set H1NEWS_API_KEY (https://heliusone.com/newsapi)")

    async with AsyncH1News(key) as news:
        print(f"listening for halts{' on ' + ', '.join(sorted(watch)) if watch else ''}…")
        async for halt in news.stream(categories=["halts"], tickers=sorted(watch) or None):
            symbols = halt.get("tickers") or []
            if watch and not (set(symbols) & watch):
                continue
            sym = symbols[0] if symbols else "?"
            reason = _REASON.search(halt.get("title", ""))
            resumed = "resum" in halt.get("title", "").lower()

            # Context: what was said about this name in the last few hours.
            context = []
            if sym != "?":
                try:
                    page = await news.news(sym, date="today", exclude_category=["halts"], limit=3)
                    context = page.get("results", [])
                except Exception as exc:  # keep alerting even if context fails
                    print(f"  (context lookup failed: {exc})")

            lines = [
                f"{'▶ RESUMED' if resumed else '⏸ HALTED'} {sym} — {halt.get('title')}",
                f"   reason {reason.group(1) if reason else '?'} · {halt.get('published_at')} · {halt.get('url')}",
            ]
            for a in context:
                lines.append(f"   ↳ [{a['sentiment']['label']}] {a['source']}: {a['title']}")
            text = "\n".join(lines)
            print(text, flush=True)
            if webhook:
                try:
                    _post(webhook, text)
                except Exception as exc:
                    print(f"  (webhook failed: {exc})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", nargs="*", default=[], help="only alert on these symbols")
    args = ap.parse_args()
    try:
        asyncio.run(main({s.upper() for s in args.watch}, os.environ.get("ALERT_WEBHOOK_URL")))
    except KeyboardInterrupt:
        pass
