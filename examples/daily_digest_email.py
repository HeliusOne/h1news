#!/usr/bin/env python3
"""Daily digest emailer — one HTML email at the close with the day in five parts:
most-mentioned tickers, the Sundown Digest, halts, regulator actions, and the
most negative headlines on your watchlist. Cron it at 21:30 UTC on weekdays.

    pip install h1news
    export H1NEWS_API_KEY=sk_...
    export ANTHROPIC_API_KEY=sk-ant-...        # optional: generates the digest if today's isn't cached yet
    export DIGEST_TO=you@example.com DIGEST_FROM=digest@example.com
    export SMTP_HOST=smtp.example.com SMTP_PORT=587 SMTP_USER=... SMTP_PASS=...
    python examples/daily_digest_email.py --watch NVDA AAPL TSLA
    python examples/daily_digest_email.py --watch NVDA --print     # render to stdout, no email

Six to nine API calls per run. Basic plan is enough (one ticker per call).
"""
from __future__ import annotations

import argparse
import html
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from h1news import H1News, H1NewsError


def esc(s: object) -> str:
    return html.escape(str(s or ""))


def rows(articles: list[dict], n: int = 8) -> str:
    if not articles:
        return "<p style='color:#888'>Nothing today.</p>"
    out = []
    for a in articles[:n]:
        s = a.get("sentiment", {}).get("label", "neutral")
        colour = {"positive": "#15803d", "negative": "#b91c1c"}.get(s, "#6b7280")
        out.append(
            f"<li style='margin:6px 0'><a href='{esc(a['url'])}' style='color:#111;text-decoration:none'>{esc(a['title'])}</a>"
            f"<br><span style='font-size:12px;color:#6b7280'>{esc(a['source'])} · "
            f"<span style='color:{colour}'>{s}</span> · {esc(', '.join(a.get('tickers', [])[:4]))}</span></li>"
        )
    return "<ul style='padding-left:18px;margin:0'>" + "".join(out) + "</ul>"


def build(news: H1News, watch: list[str]) -> tuple[str, str]:
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    parts: list[str] = [f"<h1 style='font-size:20px;margin:0 0 4px'>Market digest — {today}</h1>"
                        f"<p style='color:#6b7280;margin:0 0 18px'>H1 News API · all times UTC</p>"]

    top = news.top_mentioned("today", 10)["results"]
    parts.append("<h2 style='font-size:15px;margin:18px 0 6px'>Most mentioned</h2><p style='margin:0'>"
                 + " · ".join(f"<b>{esc(t['ticker'])}</b> {t['mentions']}" for t in top) + "</p>")

    try:
        digest = news.sundown_digest()
        body = digest.get("digest") or digest.get("text") or digest.get("summary") or ""
        if body:
            parts.append("<h2 style='font-size:15px;margin:18px 0 6px'>Sundown Digest</h2>"
                         f"<div style='white-space:pre-wrap;line-height:1.5'>{esc(body)}</div>")
    except H1NewsError as exc:
        parts.append(f"<p style='color:#888'>Sundown Digest unavailable ({esc(exc.detail)}).</p>")

    parts.append("<h2 style='font-size:15px;margin:18px 0 6px'>Trading halts</h2>"
                 + rows(news.halts(date="today", limit=8)["results"]))
    parts.append("<h2 style='font-size:15px;margin:18px 0 6px'>Regulators</h2>"
                 + rows(news.news(category="regulatory", date="today", limit=8)["results"]))

    for sym in watch:
        neg = news.news(sym, date="today", sentiment="negative", limit=5)["results"]
        pos = news.news(sym, date="today", sentiment="positive", limit=3)["results"]
        parts.append(f"<h2 style='font-size:15px;margin:18px 0 6px'>{esc(sym)}</h2>" + rows(neg + pos))

    html_body = ("<div style='font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:640px;"
                 "margin:0 auto;padding:20px;color:#111'>" + "".join(parts) +
                 "<p style='color:#9ca3af;font-size:12px;margin-top:24px'>Built with the H1 News API — "
                 "<a href='https://heliusone.com/newsapi' style='color:#9ca3af'>heliusone.com/newsapi</a></p></div>")
    return f"Market digest — {today}", html_body


def send(subject: str, html_body: str) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, os.environ["DIGEST_FROM"], os.environ["DIGEST_TO"]
    msg.set_content("Open in an HTML mail client.")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        if os.environ.get("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        smtp.send_message(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", nargs="*", default=[], help="tickers to include, one section each")
    ap.add_argument("--print", action="store_true", help="print the HTML instead of emailing")
    args = ap.parse_args()
    key = os.environ.get("H1NEWS_API_KEY") or exit("set H1NEWS_API_KEY")
    subject, body = build(H1News(key, anthropic_key=os.environ.get("ANTHROPIC_API_KEY")),
                          [s.upper() for s in args.watch])
    if args.print:
        print(body)
    else:
        send(subject, body)
        print("sent:", subject)
