import os
from datetime import datetime

import httpx

from news.models import RawArticle

_AV_BASE = "https://www.alphavantage.co/query"


def map_av_sentiment(label: str) -> str:
    if label in ("Bullish", "Somewhat-Bullish"):
        return "positive"
    if label in ("Bearish", "Somewhat-Bearish"):
        return "negative"
    return "neutral"


def _parse_av_date(dt_str: str) -> str:
    """Convert AV format YYYYMMDDTHHMMSS to ISO-8601."""
    try:
        return datetime.strptime(dt_str, "%Y%m%dT%H%M%S").isoformat()
    except ValueError:
        return dt_str


async def symbol_search(query: str) -> str | None:
    """Return the best-match ticker for a symbol or company name query."""
    api_key = os.environ["ALPHAVANTAGE_API_KEY"]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(_AV_BASE, params={
            "function": "SYMBOL_SEARCH",
            "keywords": query,
            "apikey": api_key,
        })
        r.raise_for_status()
    data = r.json()
    for error_key in ("Note", "Information", "Error Message"):
        if error_key in data:
            raise RuntimeError(f"Alpha Vantage API error: {data[error_key]}")
    matches = data.get("bestMatches", [])
    if not matches:
        return None
    # Narrow to US equities; fall back to all matches if none qualify
    candidates = [
        m for m in matches
        if m.get("4. region") == "United States" and m.get("3. type") == "Equity"
    ] or matches
    # Among candidates whose name starts with the query, prefer the shortest name.
    # This resolves ambiguity like "Apple Inc" (AAPL) vs "Apple Hospitality REIT Inc"
    # (APLE), both of which AV returns for "Apple" but with APLE ranked higher by
    # its match-score algorithm.
    query_lower = query.lower()
    name_match = [m for m in candidates if m.get("2. name", "").lower().startswith(query_lower)]
    pool = name_match if name_match else candidates
    return min(pool, key=lambda m: len(m.get("2. name", "")))["1. symbol"]


async def fetch_news(ticker: str) -> list[RawArticle]:
    """Fetch news articles with sentiment from Alpha Vantage NEWS_SENTIMENT endpoint."""
    api_key = os.environ["ALPHAVANTAGE_API_KEY"]
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(_AV_BASE, params={
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "sort": "LATEST",
            "limit": "50",
            "apikey": api_key,
        })
        r.raise_for_status()
    data = r.json()
    for error_key in ("Note", "Information", "Error Message"):
        if error_key in data:
            raise RuntimeError(f"Alpha Vantage API error: {data[error_key]}")
    return [
        RawArticle(
            title=item.get("title", ""),
            source=item.get("source", ""),
            published_at=_parse_av_date(item.get("time_published", "")),
            url=item.get("url", ""),
            summary=item.get("summary", ""),
            sentiment=map_av_sentiment(item.get("overall_sentiment_label", "")),
            source_api="alphavantage",
        )
        for item in data.get("feed", [])
    ]
