import asyncio
import os
import re

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from news.aggregator import merge
from news.alphavantage import fetch_news as av_fetch_news
from news.alphavantage import symbol_search
from news.finnhub import fetch_news as fh_fetch_news

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")

for _key in ("ALPHAVANTAGE_API_KEY", "FINNHUB_API_KEY"):
    if not os.environ.get(_key):
        raise RuntimeError(f"Missing required environment variable: {_key}")

mcp = FastMCP("stock-news")


@mcp.custom_route("/health/", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool
async def get_stock_news(query: str) -> dict:
    """Get the latest news and sentiment for a stock symbol or company name.

    Args:
        query: A ticker symbol (e.g. 'AAPL') or company name (e.g. 'Apple').

    Returns:
        A dict with 'ticker', 'news' (list of articles), and optional 'warnings'.
    """
    # Skip SYMBOL_SEARCH if query is already a ticker (saves one AV API call)
    if _TICKER_RE.match(query):
        ticker = query
    else:
        ticker = await symbol_search(query)
        if not ticker:
            return {"error": f"No ticker found for query: {query}"}
        # Respect AV free-tier 1 req/sec burst limit between the two AV calls
        await asyncio.sleep(1.2)

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
        msg = "Both news sources unavailable"
        if warnings:
            msg += ": " + "; ".join(warnings)
        raise ValueError(msg)

    news = merge(av_articles, fh_articles, ticker)
    result: dict = {"ticker": ticker, "news": [item.to_dict() for item in news]}
    if warnings:
        result["warnings"] = warnings
    return result


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    mcp.run(transport="http", host="0.0.0.0", port=port)
