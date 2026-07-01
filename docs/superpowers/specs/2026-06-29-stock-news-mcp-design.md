# Stock News MCP Server — Design Spec

**Date:** 2026-06-29  
**Last updated:** 2026-06-30  
**Status:** Implemented

---

## Overview

A FastMCP server deployed on Google Cloud Run that exposes a single MCP tool: `get_stock_news`. Given a stock ticker symbol or company name, it fetches the latest news articles from Alpha Vantage and Finnhub, merges and deduplicates them, and returns up to 10 results with API-provided sentiment labels and a `source_api` field identifying each article's origin.

---

## Tool Interface

### `get_stock_news(query: str) -> dict`

- `query` — a ticker symbol (e.g. `AAPL`) or company name (e.g. `Apple`)
- Returns a dict with `ticker`, `news` list, and optional `warnings`

**`NewsItem` shape:**
```json
{
  "title": "string",
  "source": "string",
  "published_at": "ISO-8601 string",
  "url": "string",
  "summary": "string",
  "sentiment": "positive | negative | neutral",
  "ticker": "string",
  "source_api": "alphavantage | finnhub"
}
```

**Response shape:**
```json
{
  "ticker": "AAPL",
  "news": [ ...NewsItem... ],
  "warnings": [ "alphavantage unavailable: ..." ]
}
```
`warnings` is omitted when both sources succeed.

---

## Architecture

```
main.py               # FastMCP app init + get_stock_news tool definition
news/
  __init__.py
  models.py           # RawArticle, NewsItem dataclasses
  alphavantage.py     # symbol_search(query) → str | None
                      # fetch_news(ticker) → list[RawArticle]
                      # map_av_sentiment(label) → str
  finnhub.py          # fetch_news(ticker) → list[RawArticle]
                      # map_fh_sentiment(score) → str
  aggregator.py       # merge(av, fh, ticker, per_source=5) → list[NewsItem]
```

Environment variables (required at startup, raise `RuntimeError` if absent):
- `ALPHAVANTAGE_API_KEY`
- `FINNHUB_API_KEY`

---

## Data Flow

1. **Symbol resolution** — if `query` matches `^[A-Z]{1,5}$` it is used directly as the ticker (saves one AV API call). Otherwise `alphavantage.symbol_search(query)` calls AV's `SYMBOL_SEARCH` endpoint; a 1.2 s delay is inserted before the next AV call to respect the free-tier burst limit.
2. **Parallel fetch** — `asyncio.gather` calls `alphavantage.fetch_news(ticker)` and `finnhub.fetch_news(ticker)` concurrently.
   - AV uses the `NEWS_SENTIMENT` endpoint (`sort=LATEST`, `limit=50`) with `overall_sentiment_label`
   - Finnhub uses `/company-news` (last 7 days); free tier has no per-article sentiment, so all Finnhub articles default to `"neutral"`
3. **Aggregation** — `aggregator.merge()`:
   - Caps each source at `per_source` articles (default 5) before combining
   - Deduplicates by URL across the capped sets
   - Sorts by `published_at` descending
   - Returns all remaining articles (max `2 × per_source = 10`)

**Sentiment mapping:**

| Source | Raw value | Mapped to |
|---|---|---|
| Alpha Vantage | `"Bullish"`, `"Somewhat-Bullish"` | `"positive"` |
| Alpha Vantage | `"Bearish"`, `"Somewhat-Bearish"` | `"negative"` |
| Alpha Vantage | anything else | `"neutral"` |
| Finnhub | (free tier — no per-article score) | `"neutral"` |

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing API key env var | Raise `RuntimeError` at import time naming the var |
| Query is ticker-like (`^[A-Z]{1,5}$`) | Skip `SYMBOL_SEARCH`, use query directly |
| No ticker match for company name | Return `{"error": "No ticker found for query: <query>"}` |
| AV returns `Note` / `Information` key | Raise `RuntimeError` with AV's message (surfaces rate limit errors) |
| One API fails / times out | Add entry to `warnings`, continue with other source |
| Both APIs fail | Raise `ValueError` with combined warning messages |

---

## Testing

- **Unit:** `aggregator.merge()` — per-source cap, dedup by URL, sort order, `source_api` propagation
- **Unit:** Sentiment mapping — `map_av_sentiment` (all 5 AV labels) and `map_fh_sentiment` (score thresholds)
- **Integration:** Behind `RUN_INTEGRATION_TESTS=1` env flag; hits real APIs with `AAPL`, asserts `NewsItem` shape and field values
- HTTP calls are not mocked at the unit level — tests pass pre-built `RawArticle` lists directly to the aggregator

---

## Deployment

- Containerized with `Dockerfile` using `python:3.13-slim` and `uv`
- FastMCP server listens on `$PORT` (default 8080)
- Transport: `http` (streamable HTTP, POST `/mcp`) or `sse` (SSE, GET `/sse`) — configured in `main.py`; choose based on MCP client support
- API keys injected via Cloud Run environment variables or Secret Manager
- Stateless: no local caching, all data fetched at request time

---

## Alpha Vantage Free-Tier Constraints

- 25 API requests/day, 5/minute, 1/second burst
- Each company-name query costs 2 AV calls (`SYMBOL_SEARCH` + `NEWS_SENTIMENT`)
- Each ticker query costs 1 AV call (`NEWS_SENTIMENT` only)
- Rate limit responses carry a `Note` or `Information` key — now surfaced as errors rather than silent empty results
