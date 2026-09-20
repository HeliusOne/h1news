#!/usr/bin/env python3
"""Sentiment dashboard — a Streamlit page over /v1/sentiment, /v1/news and
/v1/top-mentioned. Type a ticker, get the daily sentiment trend, the latest
headlines colour-coded by sentiment, and what the whole market is talking about.

    pip install h1news streamlit pandas
    export H1NEWS_API_KEY=sk_...
    streamlit run examples/sentiment_dashboard.py

Works on the Basic plan (one ticker per call, 30 days of history).
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from h1news import H1News, H1NewsError

st.set_page_config(page_title="H1 News — Sentiment", page_icon="📰", layout="wide")

key = os.environ.get("H1NEWS_API_KEY") or st.sidebar.text_input("H1 News API key", type="password")
if not key:
    st.info("Set H1NEWS_API_KEY or paste a key in the sidebar — get one at https://heliusone.com/newsapi")
    st.stop()


@st.cache_resource
def client(k: str) -> H1News:
    return H1News(k)


@st.cache_data(ttl=120)
def sentiment(k: str, ticker: str | None, window: str) -> pd.DataFrame:
    rows = client(k).sentiment(ticker, window)["daily"]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    return df


@st.cache_data(ttl=60)
def headlines(k: str, ticker: str, window: str, label: str | None) -> list[dict]:
    return client(k).news(ticker, date=window, sentiment=label, limit=25)["results"]


@st.cache_data(ttl=300)
def top(k: str, window: str) -> pd.DataFrame:
    return pd.DataFrame(client(k).top_mentioned(window, 15)["results"])


news = client(key)
st.title("📰 Sentiment dashboard")
ticker = st.sidebar.text_input("Ticker", "NVDA").strip().upper()
window = st.sidebar.selectbox("Window", ["today", "yesterday", "last7days", "last30days"], index=2)
label = st.sidebar.selectbox("Headlines", ["all", "positive", "negative", "neutral"])

try:
    left, right = st.columns([2, 1])
    with left:
        st.subheader(f"{ticker} · daily sentiment ({window})")
        df = sentiment(key, ticker, window)
        if df.empty:
            st.write("No articles in this window.")
        else:
            st.bar_chart(df[["positive", "neutral", "negative"]], color=["#34d399", "#94a3b8", "#f87171"])
            st.line_chart(df[["avg_score"]])
            st.caption(f"{int(df['total'].sum())} articles · avg score {df['avg_score'].mean():+.3f} (−1 … +1)")

        st.subheader("Headlines")
        for a in headlines(key, ticker, window, None if label == "all" else label):
            s = a["sentiment"]["label"]
            badge = {"positive": "🟢", "negative": "🔴"}.get(s, "⚪")
            st.markdown(f"{badge} **[{a['title']}]({a['url']})**  \n"
                        f"<span style='color:#888;font-size:0.85em'>{a['source']} · {a['category']} · "
                        f"{a['published_at'][:16].replace('T', ' ')} UTC · {', '.join(a['tickers'][:5])}</span>",
                        unsafe_allow_html=True)

    with right:
        st.subheader(f"Market sentiment ({window})")
        mkt = sentiment(key, None, window)
        if not mkt.empty:
            tot = mkt[["positive", "neutral", "negative"]].sum()
            st.bar_chart(tot)
        st.subheader("Most mentioned")
        t = top(key, window)
        if not t.empty:
            st.dataframe(t.set_index("ticker"), use_container_width=True)
        u = news.usage()
        st.caption(f"Plan {u['plan']} · {u['used_this_month']:,} of {u['monthly_quota'] or '∞'} calls this month")
except H1NewsError as exc:
    st.error(f"{exc.status}: {exc.detail}")
