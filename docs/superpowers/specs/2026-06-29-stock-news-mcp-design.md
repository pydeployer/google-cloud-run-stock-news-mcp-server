# Stock News MCP Server — Design Spec

**Date:** 2026-06-29
**Status:** Approved

---

## Overview

A FastMCP server deployed on Google Cloud Run that exposes a single MCP tool: `get_stock_news`. Given a stock ticker symbol or company name, it fetches the latest news articles from Alpha Vantage and Finnhub, merges and deduplicates them, and returns the top 10 results with API-provided sentiment labels.

---

## Tool Interface

### `get_stock_news(query: str) -> list[NewsItem]`

- `query` — a ticker symbol (e.g. `AAPL`) or company name (e.g. `Apple`)
- Returns up to 10 `NewsItem` objects, or an error/warning structure if sources fail

**`NewsItem` shape:**
```json
{
  "title": "string",
  "source": "string",
  "published_at": "ISO-8601 string",
  "url": "string",
  "summary": "string",
  "sentiment": "positive | negative | neutral",
  "ticker": "string"
}
```

---

## Architecture

```
main.py               # FastMCP app init + get_stock_news tool definition
news/
  __init__.py
  alphavantage.py     # symbol_search(query) → str (ticker)
                      # fetch_news(ticker) → list[RawArticle]
  finnhub.py          # fetch_news(ticker) → list[RawArticle]
  aggregator.py       # merge(av, fh) → list[NewsItem] (dedup, sort, top-10)
```

Environment variables (required at startup):
- `ALPHAVANTAGE_API_KEY`
- `FINNHUB_API_KEY`

---

## Data Flow

1. **Symbol resolution** — `alphavantage.symbol_search(query)` calls AV's `SYMBOL_SEARCH` endpoint and returns the best-match ticker. Raises if no match found.
2. **Parallel fetch** — `asyncio.gather` calls `alphavantage.fetch_news(ticker)` and `finnhub.fetch_news(ticker)` concurrently.
   - AV uses the `NEWS_SENTIMENT` endpoint (returns up to 50 articles with `overall_sentiment_label`)
   - Finnhub uses `/company-news` (last 7 days, returns a numeric `sentiment` score)
3. **Aggregation** — `aggregator.merge()` deduplicates by URL, sorts by `published_at` descending, returns top 10.

**Sentiment mapping:**

| Source | Raw value | Mapped to |
|---|---|---|
| Alpha Vantage | `"Bullish"` | `"positive"` |
| Alpha Vantage | `"Bearish"` | `"negative"` |
| Alpha Vantage | anything else | `"neutral"` |
| Finnhub | score > 0 | `"positive"` |
| Finnhub | score < 0 | `"negative"` |
| Finnhub | score = 0 | `"neutral"` |

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing API key env var | Raise at import time with message naming the var |
| No ticker match for query | Return `{"error": "No ticker found for query: <query>"}` |
| One API fails / times out | Log warning, continue with other source; include `"warnings"` in response |
| Rate limit (429) from one API | Treat as failure for that source; return other source results + warning |
| Both APIs fail | Raise `McpError` with descriptive message |

---

## Testing

- **Unit:** `aggregator.merge()` — dedup by URL, sort order, top-10 cap
- **Unit:** Sentiment mapping functions in both clients (label/score → string)
- **Integration:** Behind `RUN_INTEGRATION_TESTS=1` env flag; hits real APIs with `AAPL`, asserts `NewsItem` shape
- HTTP calls are not mocked at the unit level — tests feed pre-built `RawArticle` lists directly to the aggregator

---

## Deployment

- Containerized with a `Dockerfile` using `python:3.13-slim`
- FastMCP server listens on `$PORT` (default 8080)
- API keys injected via Cloud Run environment variables or Secret Manager
- Stateless: no local caching, all data fetched at request time
