"""OpenBB Platform provider for the H1 News API."""
from openbb_core.provider.abstract.provider import Provider

from openbb_h1news.models.company_news import H1NewsCompanyNewsFetcher
from openbb_h1news.models.world_news import H1NewsWorldNewsFetcher

h1news_provider = Provider(
    name="h1news",
    website="https://heliusone.com/newsapi",
    description=(
        "H1 News API: real-time, ticker-tagged, sentiment-scored financial news from "
        "135+ sources — markets, wires, central banks, regulators, SEC filings, halts, "
        "13 regions in 6 languages."
    ),
    credentials=["api_key"],
    fetcher_dict={
        "CompanyNews": H1NewsCompanyNewsFetcher,
        "WorldNews": H1NewsWorldNewsFetcher,
    },
    repr_name="H1 News API",
)
