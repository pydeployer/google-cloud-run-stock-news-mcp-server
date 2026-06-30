import os
from datetime import datetime, timedelta, timezone

import httpx

from news.models import RawArticle

_FH_BASE = "https://finnhub.io/api/v1"


def map_fh_sentiment(score: float) -> str:
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def _unix_to_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


async def fetch_news(ticker: str) -> list[RawArticle]:
    """Fetch company news from Finnhub (last 7 days). Sentiment defaults to neutral
    since per-article sentiment is not available on the free tier."""
    api_key = os.environ["FINNHUB_API_KEY"]
    today = datetime.now(tz=timezone.utc)
    from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{_FH_BASE}/company-news", params={
            "symbol": ticker,
            "from": from_date,
            "to": to_date,
            "token": api_key,
        })
        r.raise_for_status()
    items = r.json()
    if not isinstance(items, list):
        return []
    return [
        RawArticle(
            title=item.get("headline", ""),
            source=item.get("source", ""),
            published_at=_unix_to_iso(item.get("datetime", 0)),
            url=item.get("url", ""),
            summary=item.get("summary", ""),
            sentiment="neutral",
        )
        for item in items
    ]
