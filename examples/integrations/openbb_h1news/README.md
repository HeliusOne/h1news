# openbb-h1news

An [OpenBB Platform](https://docs.openbb.co/platform) provider extension that backs `obb.news.company` and `obb.news.world` with the H1 News API — ticker-tagged, sentiment-scored, 135+ sources.

```bash
pip install h1news
pip install "git+https://github.com/HeliusOne/h1news.git#subdirectory=examples/integrations/openbb_h1news"
python -c "import openbb; openbb.build()"     # rebuild the static assets so the provider shows up
```

```python
from openbb import obb
obb.user.credentials.h1news_api_key = "sk_..."

obb.news.company(symbol="NVDA", provider="h1news", limit=20).to_df()
obb.news.world(provider="h1news", limit=20, category="macro").to_df()
```

Extra query fields on top of the standard model: `sentiment` (positive | negative | neutral), `category`, `region`, `language`, `search`. Each row carries `sentiment`, `sentiment_score`, `category`, `source`, `region` and `language` beyond the standard columns.

Written against the openbb-core 1.x fetcher interface (`transform_query` / `aextract_data` / `transform_data`). If the standard models move, the shims in `models/` are the only thing to touch.
