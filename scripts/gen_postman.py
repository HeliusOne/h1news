#!/usr/bin/env python3
"""Generate examples/postman/H1-News-API.postman_collection.json from the live
OpenAPI document, so the collection never drifts from the API.

    python scripts/gen_postman.py            # reads https://api.heliusone.com/openapi.json
    python scripts/gen_postman.py openapi.json
"""
from __future__ import annotations

import json
import sys
import urllib.request
import uuid

SRC = sys.argv[1] if len(sys.argv) > 1 else "https://api.heliusone.com/openapi.json"
OUT = "examples/postman/H1-News-API.postman_collection.json"

# Example values so every request runs as-is after setting {{api_key}}.
EXAMPLES = {
    "ticker": "AAPL", "category": "earnings", "sentiment": "negative", "date": "last7days",
    "limit": "10", "search": "guidance", "form": "8-K", "source": "Federal Reserve",
    "region": "us", "language": "en", "days": "14", "active_only": "true",
}
FOLDERS = [
    ("News", ["/v1/news", "/v1/news/general", "/v1/news/earnings", "/v1/news/halts", "/v1/news/filings",
              "/v1/news/macro", "/v1/news/category/{category}", "/v1/news/{article_id}"]),
    ("Analytics", ["/v1/sentiment", "/v1/top-mentioned", "/v1/earnings-calendar", "/v1/ratings", "/v1/sundown-digest"]),
    ("Reference", ["/v1/tickers", "/v1/sources", "/v1/categories", "/v1/usage", "/health"]),
    ("Stream", ["/v1/stream/token"]),
]


def load(src: str) -> dict:
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=20) as r:
            return json.load(r)
    return json.load(open(src))


def request(path: str, method: str, op: dict) -> dict:
    query = []
    for p in op.get("parameters", []):
        if p.get("in") != "query" or p["name"] == "api_key":
            continue
        query.append({
            "key": p["name"], "value": EXAMPLES.get(p["name"], ""),
            "description": p.get("description", ""),
            "disabled": p["name"] not in ("ticker", "limit", "date", "days", "form", "active_only"),
        })
    url_path = path.replace("{category}", "regulatory").replace("{article_id}", "1")
    headers = [] if path == "/health" else [{"key": "X-API-Key", "value": "{{api_key}}"}]
    if path == "/v1/sundown-digest":
        headers.append({"key": "X-Anthropic-Key", "value": "{{anthropic_key}}", "disabled": True,
                        "description": "Only needed to generate a fresh digest (cache miss or refresh=true)"})
    return {
        "name": op.get("summary") or f"{method.upper()} {path}",
        "request": {
            "method": method.upper(),
            "header": headers,
            "url": {"raw": "{{base_url}}" + url_path + ("?" + "&".join(f"{q['key']}={q['value']}" for q in query if not q["disabled"]) if any(not q["disabled"] for q in query) else ""),
                    "host": ["{{base_url}}"], "path": url_path.strip("/").split("/"), "query": query},
            "description": op.get("description", ""),
        },
    }


def main() -> None:
    spec = load(SRC)
    paths = spec["paths"]
    items = []
    for folder, plist in FOLDERS:
        entries = []
        for p in plist:
            for method, op in paths.get(p, {}).items():
                entries.append(request(p, method, op))
        items.append({"name": folder, "item": entries})
    collection = {
        "info": {
            "_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "https://api.heliusone.com/postman")),
            "name": "H1 News API",
            "description": ("Real-time, ticker-tagged, sentiment-scored financial news from 135+ sources. "
                            "Set the `api_key` collection variable (get one at https://heliusone.com/newsapi). "
                            "Full reference: https://api.heliusone.com/docs. The WebSocket stream "
                            "(wss://api.heliusone.com/v1/stream?api_key=…) is not a REST request — use Postman's "
                            "WebSocket client, or mint a token with the Stream folder for a browser."),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": [
            {"key": "base_url", "value": "https://api.heliusone.com"},
            {"key": "api_key", "value": "", "description": "Your H1 News API key"},
            {"key": "anthropic_key", "value": "", "description": "Optional: only to generate the Sundown Digest"},
        ],
    }
    with open(OUT, "w") as f:
        json.dump(collection, f, indent=2)
    print(f"wrote {OUT}: {sum(len(i['item']) for i in items)} requests")


if __name__ == "__main__":
    main()
