# google-cloud-run-stock-news-mcp-server

A FastMCP server that fetches the latest stock news and sentiment for a given ticker symbol or company name, deployed on Google Cloud Run. News is sourced from [Alpha Vantage](https://www.alphavantage.co) and [Finnhub](https://finnhub.io) free-tier APIs.

## Tool

### `get_stock_news(query: str)`

Accepts a ticker symbol (e.g. `AAPL`) or company name (e.g. `Apple`). Returns up to 10 news articles merged from both sources, sorted by date descending.

**Response fields per article:**

| Field | Type | Description |
|---|---|---|
| `title` | string | Article headline |
| `source` | string | Publisher name |
| `published_at` | string | ISO-8601 datetime |
| `url` | string | Link to the article |
| `summary` | string | One-sentence snippet |
| `sentiment` | string | `positive`, `negative`, or `neutral` |
| `ticker` | string | Resolved stock symbol |
| `source_api` | string | `alphavantage` or `finnhub` |

Sentiment is derived from Alpha Vantage's `overall_sentiment_label`. Finnhub free-tier does not provide per-article sentiment, so all Finnhub articles default to `neutral`.

## Prerequisites

- Free API keys from [Alpha Vantage](https://www.alphavantage.co/support/#api-key) and [Finnhub](https://finnhub.io/register)
- Python 3.13
- [uv](https://docs.astral.sh/uv/)

## Local Development

```bash
uv sync

ALPHAVANTAGE_API_KEY=your_key \
FINNHUB_API_KEY=your_key \
uv run python main.py
```

The MCP server starts on `http://0.0.0.0:8080`.

**Transport:** `main.py` defaults to `transport="http"` (streamable HTTP, POST `/mcp`). Change to `transport="sse"` if your MCP client expects SSE (GET `/sse`).

## Running Tests

```bash
# Unit tests (no API keys required)
uv run pytest tests/test_aggregator.py tests/test_sentiment.py -v

# Integration tests (hits real APIs)
ALPHAVANTAGE_API_KEY=your_key \
FINNHUB_API_KEY=your_key \
RUN_INTEGRATION_TESTS=1 \
uv run pytest tests/test_integration.py -v
```

## Docker

```bash
docker build -t stock-news-mcp .

docker run --rm \
  -e ALPHAVANTAGE_API_KEY=your_key \
  -e FINNHUB_API_KEY=your_key \
  -p 8080:8080 \
  stock-news-mcp
```

## Deploy to Google Cloud Run

```bash
gcloud run deploy stock-news-mcp \
  --source . \
  --region us-central1 \
  --set-env-vars ALPHAVANTAGE_API_KEY=your_key,FINNHUB_API_KEY=your_key \
  --allow-unauthenticated
```

## Alpha Vantage Free-Tier Limits

- 25 requests/day, 1 request/second burst
- Ticker queries (e.g. `AAPL`) use **1** AV call; company-name queries (e.g. `Apple`) use **2** (symbol search + news)
- A 1.2 s gap is automatically inserted between the two calls for company-name queries
