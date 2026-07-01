from news.models import RawArticle
from news.aggregator import merge


def _article(url: str, published_at: str, sentiment: str = "neutral", source_api: str = "alphavantage") -> RawArticle:
    return RawArticle(
        title=f"Title {url}",
        source="TestSource",
        published_at=published_at,
        url=url,
        summary="A summary.",
        sentiment=sentiment,
        source_api=source_api,
    )


def test_merge_deduplicates_by_url():
    a = _article("http://example.com/1", "2024-01-02T00:00:00")
    b = _article("http://example.com/1", "2024-01-02T00:00:00")  # same URL
    result = merge([a], [b], ticker="AAPL")
    assert len(result) == 1


def test_merge_sorts_by_date_descending():
    a1 = _article("http://example.com/1", "2024-01-01T00:00:00")
    a2 = _article("http://example.com/2", "2024-01-03T00:00:00")
    a3 = _article("http://example.com/3", "2024-01-02T00:00:00")
    result = merge([a1, a2], [a3], ticker="AAPL")
    assert result[0].published_at == "2024-01-03T00:00:00"
    assert result[1].published_at == "2024-01-02T00:00:00"
    assert result[2].published_at == "2024-01-01T00:00:00"


def test_merge_caps_at_default_limit():
    articles = [_article(f"http://example.com/{i}", "2024-01-01T00:00:00") for i in range(15)]
    result = merge(articles, [], ticker="AAPL")
    assert len(result) == 10


def test_merge_respects_custom_limit():
    articles = [_article(f"http://example.com/{i}", "2024-01-01T00:00:00") for i in range(5)]
    result = merge(articles, [], ticker="AAPL", limit=3)
    assert len(result) == 3


def test_merge_attaches_ticker():
    a = _article("http://example.com/1", "2024-01-01T00:00:00")
    result = merge([a], [], ticker="TSLA")
    assert result[0].ticker == "TSLA"


def test_merge_empty_sources_returns_empty():
    assert merge([], [], ticker="AAPL") == []


def test_merge_returns_newsitem_with_all_fields():
    a = _article("http://example.com/1", "2024-01-01T00:00:00", sentiment="positive", source_api="alphavantage")
    result = merge([a], [], ticker="AAPL")
    item = result[0]
    assert item.title == "Title http://example.com/1"
    assert item.source == "TestSource"
    assert item.url == "http://example.com/1"
    assert item.summary == "A summary."
    assert item.sentiment == "positive"
    assert item.ticker == "AAPL"
    assert item.source_api == "alphavantage"


def test_merge_preserves_source_api():
    av = _article("http://example.com/1", "2024-01-02T00:00:00", source_api="alphavantage")
    fh = _article("http://example.com/2", "2024-01-01T00:00:00", source_api="finnhub")
    result = merge([av], [fh], ticker="AAPL")
    assert result[0].source_api == "alphavantage"
    assert result[1].source_api == "finnhub"
