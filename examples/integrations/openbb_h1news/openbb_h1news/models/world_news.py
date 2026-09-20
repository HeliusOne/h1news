"""obb.news.world(provider="h1news")"""
from __future__ import annotations

from typing import Any, Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.world_news import WorldNewsData, WorldNewsQueryParams

from openbb_h1news.models._common import H1ExtraDataFields, H1ExtraQueryFields, article_row, client


class H1NewsWorldNewsQueryParams(WorldNewsQueryParams, H1ExtraQueryFields):
    pass


class H1NewsWorldNewsData(WorldNewsData, H1ExtraDataFields):
    pass


class H1NewsWorldNewsFetcher(Fetcher[H1NewsWorldNewsQueryParams, list[H1NewsWorldNewsData]]):
    @staticmethod
    def transform_query(params: dict[str, Any]) -> H1NewsWorldNewsQueryParams:
        return H1NewsWorldNewsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: H1NewsWorldNewsQueryParams,
        credentials: Optional[dict[str, str]],
        **kwargs: Any,
    ) -> list[dict]:
        news = client(credentials)
        page = news.general(
            since=query.start_date, until=query.end_date, sentiment=query.sentiment,
            region=query.region, language=query.language, limit=min(query.limit or 20, 200),
        ) if not (query.category or query.search) else news.news(
            since=query.start_date, until=query.end_date, sentiment=query.sentiment,
            category=query.category, region=query.region, language=query.language,
            search=query.search, limit=min(query.limit or 20, 200),
        )
        return page["results"]

    @staticmethod
    def transform_data(
        query: H1NewsWorldNewsQueryParams, data: list[dict], **kwargs: Any
    ) -> list[H1NewsWorldNewsData]:
        return [H1NewsWorldNewsData(**article_row(a)) for a in data]
