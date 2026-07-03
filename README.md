# google-cloud-run-stock-news-mcp-server

A FastMCP server that fetches the latest stock news and sentiment for a given ticker symbol or company name, deployed on Google Cloud Run. News is sourced from [Alpha Vantage](https://www.alphavantage.co) and [Finnhub](https://finnhub.io) free-tier APIs.

## Prerequisites

- Free API keys from [Alpha Vantage](https://www.alphavantage.co/support/#api-key) and [Finnhub](https://finnhub.io/register)
- Python 3.14
- [uv](https://docs.astral.sh/uv/)

> **Note:** Alpha Vantage free tier allows 25 requests/day with a 1 request/second burst limit. Ticker queries (e.g. `AAPL`) use **1** AV call; company-name queries (e.g. `Apple`) use **2** (symbol search + news). A 1.2 s gap is automatically inserted between the two calls for company-name queries.

## Local Development

```bash
uv sync

ALPHAVANTAGE_API_KEY=your_key \
FINNHUB_API_KEY=your_key \
uv run python main.py
```

The MCP server starts on `http://0.0.0.0:8080`.

**Transport:** `main.py` defaults to `transport="http"` (streamable HTTP, POST `/mcp`). Change to `transport="sse"` if your MCP client expects SSE (GET `/sse`).

## pytest

```bash
# Unit tests (no API keys required)
uv run pytest tests/test_aggregator.py tests/test_sentiment.py -v

# Integration tests (hits real APIs)
ALPHAVANTAGE_API_KEY=your_key \
FINNHUB_API_KEY=your_key \
RUN_INTEGRATION_TESTS=1 \
uv run pytest tests/test_integration.py -v
```

## Tool

Tested with [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) — connect it to `http://localhost:8080/mcp` (streamable HTTP) or `http://localhost:8080/sse` (SSE) depending on your transport setting.

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

**Example response** for `query="NVDA"`:

<details>
<summary>Show sample output</summary>

```json
{
  "ticker": "NVDA",
  "news": [
    {
      "title": "Did Broad Russell Index Removal Just Reframe Lumentum Holdings' (LITE) AI-Focused Investment Narrative?",
      "source": "Simply Wall Street",
      "published_at": "2026-07-01T02:39:53",
      "url": "https://simplywall.st/stocks/us/tech/nasdaq-lite/lumentum-holdings/news/did-broad-russell-index-removal-just-reframe-lumentum-holdin",
      "summary": "Lumentum Holdings (LITE) was recently removed from several major Russell indices, potentially impacting its ownership and liquidity. This exclusion occurs despite the company's efforts to position itself as an AI-focused optics and governance leader, highlighted by recent presentations. While the index removal doesn't change core business drivers like AI optics demand, it could influence trading and prompt re-evaluation of its investment narrative, especially given its concentrated exposure to hyperscale customers.",
      "sentiment": "positive",
      "ticker": "NVDA",
      "source_api": "alphavantage"
    },
    {
      "title": "Michael Burry 'Finally' Shorts Tesla Ahead Of Q2 Deliveries — Gary Black Sees A Beat But Still Won't Own The Stock",
      "source": "Yahoo",
      "published_at": "2026-07-01T01:17:11+00:00",
      "url": "https://finnhub.io/api/news?id=aa806c54aabc58792491cf21679a11974d7f62cca6e930963573e94b9d005942",
      "summary": "Burry said he shorted Tesla at $416.22 ahead of its Q2 delivery report, saying he was \"happy it jumped back to this level.\"",
      "sentiment": "neutral",
      "ticker": "NVDA",
      "source_api": "finnhub"
    },
    {
      "title": "Why AeroVironment Stock Skyrocketed Today",
      "source": "Yahoo",
      "published_at": "2026-07-01T01:10:17+00:00",
      "url": "https://finnhub.io/api/news?id=421a48c82af1363775b4b455041db4ad5e17406ec7dd048c15cc255ebe508485",
      "summary": "Unmanned vehicles are a vital part of the modern battlefield.",
      "sentiment": "neutral",
      "ticker": "NVDA",
      "source_api": "finnhub"
    },
    {
      "title": "The Crowd Is Buying Sweetgreen Stock. My Honest Take Isn't as Optimistic.",
      "source": "Yahoo",
      "published_at": "2026-07-01T00:31:00+00:00",
      "url": "https://finnhub.io/api/news?id=ccd12a2852ec8471633b03a6e3deb64a132567231e467167bf0ff6555075e436",
      "summary": "Wall Street loves Sweetgreen right now. The company's track record suggests caution, though.",
      "sentiment": "neutral",
      "ticker": "NVDA",
      "source_api": "finnhub"
    },
    {
      "title": "How Buying SpaceX Today Could 10X Your Investment",
      "source": "Yahoo",
      "published_at": "2026-07-01T00:25:00+00:00",
      "url": "https://finnhub.io/api/news?id=e30b2e4079fc2369a732f82ccc5baff31c46bca6a295989c98098087fb80234b",
      "summary": "If SpaceX unlocks this multitrillion-dollar market opportunity, the stock will take off.",
      "sentiment": "neutral",
      "ticker": "NVDA",
      "source_api": "finnhub"
    },
    {
      "title": "SpaceX Is 'Much More Of An AI Play' Than A Space Company, Says Dan Ives — Here's The Bull Case",
      "source": "Yahoo",
      "published_at": "2026-07-01T00:08:41+00:00",
      "url": "https://finnhub.io/api/news?id=24da783c10b7107a99722cbc3d80989969de87a3b1bb0a1e8c066db32e8e6cac",
      "summary": "Wedbush's Dan Ives says SpaceX could become a major AI-driven hyperscaler, while remaining bullish on semiconductors and select software stocks.",
      "sentiment": "neutral",
      "ticker": "NVDA",
      "source_api": "finnhub"
    },
    {
      "title": "Form 424B5 Realty Income Corp For: 30 June By Investing.com",
      "source": "Investing.com Canada",
      "published_at": "2026-06-30T21:50:27",
      "url": "https://ca.investing.com/news/stock-market-news/form-424b5-realty-income-corp-for-30-june-93CH-4714952",
      "summary": "The article is a financial filing notification from Investing.com about Realty Income Corp's Form 424B5 for June 30.",
      "sentiment": "neutral",
      "ticker": "NVDA",
      "source_api": "alphavantage"
    },
    {
      "title": "Axon Enterprise CEO sells $5 million in shares",
      "source": "Investing.com",
      "published_at": "2026-06-30T21:15:12",
      "url": "https://www.investing.com/news/insider-trading-news/axon-enterprise-ceo-sells-5-million-in-shares-93CH-4768965",
      "summary": "Axon Enterprise CEO, Patrick W. Smith, sold 10,000 shares worth over $5 million on June 29, 2026, as per a pre-arranged trading plan.",
      "sentiment": "positive",
      "ticker": "NVDA",
      "source_api": "alphavantage"
    },
    {
      "title": "Bit Origin (NASDAQ: BTOG) shifts to Dogecoin treasury and $11M AI servers",
      "source": "Stock Titan",
      "published_at": "2026-06-30T20:41:17",
      "url": "https://www.stocktitan.net/sec-filings/BTOG/6-k-bit-origin-ltd-current-report-foreign-issuer-59c24d95614b.html",
      "summary": "Bit Origin (NASDAQ: BTOG) is transitioning its business strategy from cryptocurrency mining to holding Dogecoin as a treasury asset and investing in AI computing infrastructure, including a commitment to purchase $11 million in NVIDIA Blackwell B300 AI servers.",
      "sentiment": "positive",
      "ticker": "NVDA",
      "source_api": "alphavantage"
    }
  ]
}
```

</details>



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
