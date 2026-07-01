# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## Project Overview

A FastMCP server that provides stock news via a single MCP tool (`get_stock_news`), deployed on Google Cloud Run. News is sourced from **Alpha Vantage** and **Finnhub** free-tier APIs.


## Architecture

```
main.py               # FastMCP app + get_stock_news tool
news/
  models.py           # RawArticle, NewsItem dataclasses
  alphavantage.py     # symbol_search(), fetch_news(), map_av_sentiment()
  finnhub.py          # fetch_news(), map_fh_sentiment()
  aggregator.py       # merge() — cap 5/source, dedup by URL, sort by date
tests/
  test_aggregator.py  # unit tests for merge logic
  test_sentiment.py   # unit tests for sentiment mapping
  test_integration.py # real-API tests (set RUN_INTEGRATION_TESTS=1)
Dockerfile            # Cloud Run container (python:3.13-slim + uv)
```

**Tool:** `get_stock_news(query: str)` — accepts a ticker (`AAPL`) or company name (`Apple`). Returns up to 10 articles merged from both sources, each with `title`, `source`, `published_at`, `url`, `summary`, `sentiment` (`positive|negative|neutral`), `ticker`, and `source_api` (`alphavantage|finnhub`).

**Merge strategy:** up to 5 articles from each source → deduplicate by URL → sort by date descending → return all (max 10).

**Required env vars:** `ALPHAVANTAGE_API_KEY`, `FINNHUB_API_KEY` — validated at startup.

**Alpha Vantage free-tier notes:**
- 25 requests/day, 1 request/second burst limit
- Queries already matching `^[A-Z]{1,5}$` skip `SYMBOL_SEARCH` (saves one call)
- A 1.2 s gap is inserted between `SYMBOL_SEARCH` and `NEWS_SENTIMENT` for company-name queries
- `NEWS_SENTIMENT` returns `Note` or `Information` keys instead of `feed` when rate-limited — the client raises `RuntimeError` with the API's message rather than silently returning empty results

**Finnhub free-tier notes:**
- `/company-news` does not provide per-article sentiment; all Finnhub articles default to `"neutral"`


## Development Environment

- **Python**: 3.13 (pinned via `.python-version`)
- **Package manager**: `uv` — use `uv` for all dependency and virtualenv operations

```bash
uv sync                        # install/sync dependencies
uv add <package>               # add a dependency
uv run python main.py          # run the server (requires API keys in env)
uv run pytest                  # run unit tests
uv run pytest tests/test_integration.py  # run integration tests (requires keys + flag)
```

Run integration tests:
```bash
ALPHAVANTAGE_API_KEY=... FINNHUB_API_KEY=... RUN_INTEGRATION_TESTS=1 uv run pytest tests/test_integration.py -v
```


## Google Cloud Run Deployment

A `Dockerfile` is included. The Cloud Run service should:
- Set `PORT` to 8080 (default)
- Inject `ALPHAVANTAGE_API_KEY` and `FINNHUB_API_KEY` via Cloud Run environment variables or Secret Manager
- The FastMCP server transport is configured in `main.py` (`transport="http"` for streamable HTTP, or `transport="sse"` for SSE — change to match your MCP client)
