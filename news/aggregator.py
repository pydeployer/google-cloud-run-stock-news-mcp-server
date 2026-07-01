from datetime import datetime

from news.models import NewsItem, RawArticle


def _to_naive_utc(dt_str: str) -> datetime:
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.utcoffset() is not None:
            dt = (dt - dt.utcoffset()).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return datetime.min


def merge(
    av_articles: list[RawArticle],
    fh_articles: list[RawArticle],
    ticker: str,
    per_source: int = 5,
) -> list[NewsItem]:
    # Cap each source independently before merging
    candidates = av_articles[:per_source] + fh_articles[:per_source]
    seen: set[str] = set()
    combined: list[RawArticle] = []
    for article in candidates:
        if article.url and article.url not in seen:
            seen.add(article.url)
            combined.append(article)
    combined.sort(key=lambda a: _to_naive_utc(a.published_at), reverse=True)
    return [
        NewsItem(
            title=a.title,
            source=a.source,
            published_at=a.published_at,
            url=a.url,
            summary=a.summary,
            sentiment=a.sentiment,
            ticker=ticker,
            source_api=a.source_api,
        )
        for a in combined
    ]
