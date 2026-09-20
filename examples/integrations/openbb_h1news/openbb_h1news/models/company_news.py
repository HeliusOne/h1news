"""obb.news.company(provider="h1news")"""
from __future__ import annotations

from typing import Any, Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.company_news import CompanyNewsData, CompanyNewsQueryParams

from openbb_h1news.models._common import H1ExtraDataFields, H1ExtraQueryFields, article_row, client


class H1NewsCompanyNewsQueryParams(CompanyNewsQueryParams, H1ExtraQueryFields):
    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}


class H1NewsCompanyNewsData(CompanyNewsData, H1ExtraDataFields):
    pass


class H1NewsCompanyNewsFetcher(Fetcher[H1NewsCompanyNewsQueryParams, list[H1NewsCompanyNewsData]]):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> H1NewsCompanyNewsQueryParams:
        return H1NewsCompanyNewsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: H1NewsCompanyNewsQueryParams,
        credentials: Optional[dict[str, str]],
        **kwargs: Any,
    ) -> list[dict]:
        news = client(credentials)
        tickers = [s.strip().upper() for s in (query.symbol or "").split(",") if s.strip()]
        limit = query.limit or 20
        rows: list[dict] = []
        # Basic keys take one ticker per call; Pro keys could pass the list at
        # once. One call per symbol works on both.
        for sym in tickers or [None]:
            page = news.news(
                sym, since=query.start_date, until=query.end_date,
                sentiment=query.sentiment, category=query.category, region=query.region,
                language=query.language, search=query.search, limit=min(limit, 200),
            )
            rows.extend(page["results"])
        rows.sort(key=lambda a: a["published_at"], reverse=True)
        return rows[:limit]

    @staticmethod
    def transform_data(
        query: H1NewsCompanyNewsQueryParams, data: list[dict], **kwargs: Any
    ) -> list[H1NewsCompanyNewsData]:
        return [H1NewsCompanyNewsData(**article_row(a)) for a in data]
