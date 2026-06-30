import asyncio
import os

import pytest

from news.aggregator import merge
from news.alphavantage import fetch_news as av_fetch_news
from news.alphavantage import symbol_search
from news.finnhub import fetch_news as fh_fetch_news
from news.models import NewsItem

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


async def test_symbol_search_resolves_company_name():
    ticker = await symbol_search("Apple")
    assert ticker == "AAPL"


async def test_av_fetch_news_returns_articles_with_sentiment():
    articles = await av_fetch_news("AAPL")
    assert len(articles) > 0
    for a in articles:
        assert a.title
        assert a.url
        assert a.sentiment in ("positive", "negative", "neutral")


async def test_fh_fetch_news_returns_list():
    articles = await fh_fetch_news("AAPL")
    assert isinstance(articles, list)
    for a in articles:
        assert a.sentiment in ("positive", "negative", "neutral")
        assert a.url


async def test_full_pipeline_returns_top_10():
    ticker = await symbol_search("Apple")
    assert ticker
    av_articles, fh_articles = await asyncio.gather(
        av_fetch_news(ticker),
        fh_fetch_news(ticker),
    )
    news = merge(av_articles, fh_articles, ticker)
    assert 0 < len(news) <= 10
    for item in news:
        assert isinstance(item, NewsItem)
        assert item.ticker == ticker
        assert item.url
        assert item.title
        assert item.sentiment in ("positive", "negative", "neutral")
