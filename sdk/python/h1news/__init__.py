"""H1 News API client.

    from h1news import H1News

    news = H1News("sk_...")
    for a in news.news(ticker="AAPL", sentiment="negative", limit=5)["results"]:
        print(a["published_at"], a["source"], a["title"])

    # Live stream (Pro plan) — reconnects and backfills gaps on its own
    import asyncio
    from h1news import AsyncH1News

    async def main():
        async with AsyncH1News("sk_...") as news:
            async for a in news.stream(tickers=["AAPL", "TSLA"], categories=["earnings", "halts"]):
                print(a["title"])

    asyncio.run(main())
"""
from h1news.client import (
    AsyncH1News,
    AuthError,
    H1News,
    H1NewsError,
    PlanLimitError,
    RateLimitError,
    __version__,
)

__all__ = [
    "H1News",
    "AsyncH1News",
    "H1NewsError",
    "AuthError",
    "PlanLimitError",
    "RateLimitError",
    "__version__",
]
