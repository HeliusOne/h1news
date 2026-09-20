#!/usr/bin/env python3
"""News-reactive risk control on Alpaca — PAPER TRADING ONLY.

Streams headlines for the symbols you hold (Pro plan). When a position gets a
strongly negative headline from a primary source — an 8-K, a trading halt, a
regulator action, or a wire release scored below the threshold — it flattens
the position with a market order on Alpaca's paper API and prints what it saw.

This is a template for wiring the feed into a broker, not trading advice, and
it deliberately only ever *reduces* exposure. Keep it on paper until you've
watched it through a few sessions.

    pip install h1news alpaca-py
    export H1NEWS_API_KEY=sk_...            # Pro (the stream)
    export APCA_API_KEY_ID=... APCA_API_SECRET_KEY=...     # Alpaca PAPER keys
    python examples/integrations/alpaca_news_strategy.py --threshold -0.6 --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import os

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from h1news import AsyncH1News

# Sources whose negative headlines are about the company itself, not opinion.
PRIMARY_TYPES = {"filing", "press_release"}
PRIMARY_CATEGORIES = {"halts", "filings", "regulatory"}


async def main(threshold: float, dry_run: bool, refresh_positions_s: int) -> None:
    news_key = os.environ.get("H1NEWS_API_KEY") or exit("set H1NEWS_API_KEY")
    alpaca = TradingClient(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"], paper=True)

    def held() -> dict[str, float]:
        return {p.symbol: float(p.qty) for p in alpaca.get_all_positions() if float(p.qty) > 0}

    positions = held()
    print("holding:", ", ".join(sorted(positions)) or "nothing (add paper positions first)")
    if not positions:
        return

    async def refresher() -> None:
        nonlocal positions
        while True:
            await asyncio.sleep(refresh_positions_s)
            positions = await asyncio.to_thread(held)

    asyncio.create_task(refresher())

    async with AsyncH1News(news_key) as news:
        # Stream everything and filter locally against the live position set,
        # so a position opened mid-session is covered without resubscribing.
        async for a in news.stream(regions=["us", "global"]):
            symbols = set(a.get("tickers") or []) & set(positions)
            if not symbols:
                continue
            score = a.get("sentiment", {}).get("score", 0.0)
            primary = a.get("type") in PRIMARY_TYPES or a.get("category") in PRIMARY_CATEGORIES
            is_halt = a.get("category") == "halts"
            if not primary or (score > threshold and not is_halt):
                continue  # opinion pieces, and mild primary news, don't move risk here
            for sym in sorted(symbols):
                qty = positions.get(sym, 0)
                print(f"⚠ {sym} qty={qty} score={score:+.2f} [{a['category']}/{a['type']}] {a['source']}: {a['title']}")
                if dry_run or qty <= 0:
                    continue
                try:
                    order = alpaca.submit_order(MarketOrderRequest(
                        symbol=sym, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY,
                    ))
                    positions.pop(sym, None)
                    print(f"   → flattened {sym}: order {order.id} ({order.status})")
                except Exception as exc:
                    print(f"   → order failed: {exc}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threshold", type=float, default=-0.6, help="sentiment score at or below which to act (−1 … +1)")
    ap.add_argument("--dry-run", action="store_true", help="print, never order")
    ap.add_argument("--refresh-positions", type=int, default=300, help="seconds between position refreshes")
    args = ap.parse_args()
    try:
        asyncio.run(main(args.threshold, args.dry_run, args.refresh_positions))
    except KeyboardInterrupt:
        pass
