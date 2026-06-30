import asyncio
import os

from fastmcp import FastMCP

from news.aggregator import merge
from news.alphavantage import fetch_news as av_fetch_news
from news.alphavantage import symbol_search
from news.finnhub import fetch_news as fh_fetch_news

for _key in ("ALPHAVANTAGE_API_KEY", "FINNHUB_API_KEY"):
    if not os.environ.get(_key):
        raise RuntimeError(f"Missing required environment variable: {_key}")

mcp = FastMCP("stock-news")


@mcp.tool
async def get_stock_news(query: str) -> dict:
    """Get the latest news and sentiment for a stock symbol or company name.

    Args:
        query: A ticker symbol (e.g. 'AAPL') or company name (e.g. 'Apple').

    Returns:
        A dict with 'ticker', 'news' (list of articles), and optional 'warnings'.
    """
    ticker = await symbol_search(query)
    if not ticker:
        return {"error": f"No ticker found for query: {query}"}

    av_articles, fh_articles = [], []
    warnings: list[str] = []

    async def _fetch_av() -> None:
        nonlocal av_articles
        try:
            av_articles = await av_fetch_news(ticker)
        except Exception as exc:
            warnings.append(f"alphavantage unavailable: {exc}")

    async def _fetch_fh() -> None:
        nonlocal fh_articles
        try:
            fh_articles = await fh_fetch_news(ticker)
        except Exception as exc:
            warnings.append(f"finnhub unavailable: {exc}")

    await asyncio.gather(_fetch_av(), _fetch_fh())

    if not av_articles and not fh_articles:
        return {"error": "Both news sources returned no results", "warnings": warnings}

    news = merge(av_articles, fh_articles, ticker)
    result: dict = {"ticker": ticker, "news": [item.to_dict() for item in news]}
    if warnings:
        result["warnings"] = warnings
    return result


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    mcp.run(transport="http", host="0.0.0.0", port=port)
