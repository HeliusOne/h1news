"""Shared pieces for the H1 News fetchers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from openbb_core.provider.abstract.fetcher import Fetcher  # noqa: F401  (re-export for models)
from pydantic import Field

from h1news import H1News

BASE_URL = "https://api.heliusone.com"


def client(credentials: Optional[dict[str, Any]]) -> H1News:
    key = (credentials or {}).get("h1news_api_key")
    if not key:
        raise ValueError("Set obb.user.credentials.h1news_api_key — get a key at https://heliusone.com/newsapi")
    return H1News(key, base_url=BASE_URL)


def article_row(a: dict) -> dict:
    """Map an H1 article to the standard news columns plus H1 extras."""
    return {
        "date": datetime.fromisoformat(a["published_at"]),
        "title": a["title"],
        "text": a.get("summary") or None,
        "url": a["url"],
        "symbols": ",".join(a.get("tickers") or []) or None,
        "source": a.get("source"),
        "sentiment": (a.get("sentiment") or {}).get("label"),
        "sentiment_score": (a.get("sentiment") or {}).get("score"),
        "category": a.get("category"),
        "region": a.get("region"),
        "language": a.get("language"),
        "article_type": a.get("type"),
        "h1_id": a.get("id"),
    }


class H1ExtraQueryFields:
    """Mixin-style field definitions shared by both query models."""

    sentiment: Optional[str] = Field(default=None, description="positive | negative | neutral")
    category: Optional[str] = Field(default=None, description="markets | earnings | macro | world | commodities | forex | crypto | halts | filings | regulatory")
    region: Optional[str] = Field(default=None, description="us | uk | eu | jp | br | mx | latam | ca | au | in | cn | asia | global")
    language: Optional[str] = Field(default=None, description="ISO-639-1 code, e.g. en")
    search: Optional[str] = Field(default=None, description="Full-text search; supports AND / OR")


class H1ExtraDataFields:
    source: Optional[str] = Field(default=None, description="Publishing source")
    sentiment: Optional[str] = Field(default=None, description="positive | negative | neutral")
    sentiment_score: Optional[float] = Field(default=None, description="−1 … +1")
    category: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default=None)
    article_type: Optional[str] = Field(default=None, description="article | press_release | filing | social")
    h1_id: Optional[int] = Field(default=None, description="H1 article id (use with since_id for backfill)")
