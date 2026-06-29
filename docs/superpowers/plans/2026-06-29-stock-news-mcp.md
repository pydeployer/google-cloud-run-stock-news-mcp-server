# Stock News MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastMCP server that fetches merged, deduplicated stock news with sentiment from Alpha Vantage and Finnhub given a symbol or company name.

**Architecture:** One MCP tool (`get_stock_news`) resolves the query to a ticker via AV symbol search, then fetches news from both sources in parallel, merges and deduplicates by URL, and returns the top 10 sorted by date descending. Sentiment is taken directly from Alpha Vantage's `overall_sentiment_label`; Finnhub free-tier `/company-news` does not provide per-article sentiment so defaults to `"neutral"`.

**Tech Stack:** Python 3.13, FastMCP, httpx (async HTTP), pytest, pytest-asyncio, uv, Docker (Cloud Run).

## Global Constraints

- Python ≥ 3.13 (pinned in `.python-version`)
- Use `uv` for all dependency operations — never `pip` directly
- Env vars `ALPHAVANTAGE_API_KEY` and `FINNHUB_API_KEY` must be set; raise `RuntimeError` at import if missing
- FastMCP transport: `http`, host `0.0.0.0`, port from `$PORT` (default 8080)
- Return top 10 articles max; fields: `title`, `source`, `published_at` (ISO-8601), `url`, `summary`, `sentiment` (`"positive"|"negative"|"neutral"`), `ticker`
- No local caching — all data fetched at request time
- pytest asyncio mode: `auto` (configured in `pyproject.toml`)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Add runtime + dev deps, pytest config |
| `news/__init__.py` | Create | Package marker |
| `news/models.py` | Create | `RawArticle`, `NewsItem` dataclasses |
| `news/aggregator.py` | Create | `merge()` — dedup, sort, top-N |
| `news/alphavantage.py` | Create | `map_av_sentiment()`, `symbol_search()`, `fetch_news()` |
| `news/finnhub.py` | Create | `map_fh_sentiment()`, `fetch_news()` |
| `main.py` | Modify | FastMCP app + `get_stock_news` tool |
| `tests/__init__.py` | Create | Package marker |
| `tests/test_aggregator.py` | Create | Unit tests for merge logic |
| `tests/test_sentiment.py` | Create | Unit tests for sentiment mappers |
| `tests/test_integration.py` | Create | Integration tests (behind `RUN_INTEGRATION_TESTS=1`) |
| `Dockerfile` | Create | Cloud Run container |

---

### Task 1: Project setup — dependencies and scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `news/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: `fastmcp`, `httpx`, `pytest`, `pytest-asyncio` available; `asyncio_mode = "auto"` configured

- [ ] **Step 1: Replace pyproject.toml contents**

```toml
[project]
name = "google-cloud-run-stock-news-mcp-server"
version = "0.1.0"
description = "FastMCP stock news server with Alpha Vantage and Finnhub"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "fastmcp>=2.0",
    "httpx>=0.27",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create package markers**

```bash
mkdir -p news tests
touch news/__init__.py tests/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
uv sync
```

Expected: lock file created, `.venv` populated with fastmcp, httpx, pytest, pytest-asyncio.

- [ ] **Step 4: Verify pytest is available**

```bash
uv run pytest --version
```

Expected: `pytest X.Y.Z`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock news/__init__.py tests/__init__.py
git commit -m "chore: add fastmcp, httpx, pytest deps and project scaffolding"
```

---

### Task 2: Models — RawArticle and NewsItem dataclasses

**Files:**
- Create: `news/models.py`

**Interfaces:**
- Produces:
  - `RawArticle(title, source, published_at, url, summary, sentiment)` — internal type; `sentiment` is already mapped to `"positive"|"negative"|"neutral"`
  - `NewsItem(title, source, published_at, url, summary, sentiment, ticker)` — external return type

- [ ] **Step 1: Create `news/models.py`**

```python
from dataclasses import dataclass, asdict


@dataclass
class RawArticle:
    title: str
    source: str
    published_at: str  # ISO-8601 or AV format; normalised by each client
    url: str
    summary: str
    sentiment: str  # "positive" | "negative" | "neutral"


@dataclass
class NewsItem:
    title: str
    source: str
    published_at: str
    url: str
    summary: str
    sentiment: str
    ticker: str

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 2: Commit**

```bash
git add news/models.py
git commit -m "feat: add RawArticle and NewsItem dataclasses"
```

---

### Task 3: Aggregator — merge, dedup, sort, top-N (TDD)

**Files:**
- Create: `tests/test_aggregator.py`, `news/aggregator.py`

**Interfaces:**
- Consumes: `RawArticle` from `news.models`
- Produces: `merge(av_articles: list[RawArticle], fh_articles: list[RawArticle], ticker: str, limit: int = 10) -> list[NewsItem]`

- [ ] **Step 1: Write failing tests**

Create `tests/test_aggregator.py`:

```python
from news.models import RawArticle
from news.aggregator import merge


def _article(url: str, published_at: str, sentiment: str = "neutral") -> RawArticle:
    return RawArticle(
        title=f"Title {url}",
        source="TestSource",
        published_at=published_at,
        url=url,
        summary="A summary.",
        sentiment=sentiment,
    )


def test_merge_deduplicates_by_url():
    a = _article("http://example.com/1", "2024-01-02T00:00:00")
    b = _article("http://example.com/1", "2024-01-02T00:00:00")  # same URL
    result = merge([a], [b], ticker="AAPL")
    assert len(result) == 1


def test_merge_sorts_by_date_descending():
    a1 = _article("http://example.com/1", "2024-01-01T00:00:00")
    a2 = _article("http://example.com/2", "2024-01-03T00:00:00")
    a3 = _article("http://example.com/3", "2024-01-02T00:00:00")
    result = merge([a1, a2], [a3], ticker="AAPL")
    assert result[0].published_at == "2024-01-03T00:00:00"
    assert result[1].published_at == "2024-01-02T00:00:00"
    assert result[2].published_at == "2024-01-01T00:00:00"


def test_merge_caps_at_default_limit():
    articles = [_article(f"http://example.com/{i}", "2024-01-01T00:00:00") for i in range(15)]
    result = merge(articles, [], ticker="AAPL")
    assert len(result) == 10


def test_merge_respects_custom_limit():
    articles = [_article(f"http://example.com/{i}", "2024-01-01T00:00:00") for i in range(5)]
    result = merge(articles, [], ticker="AAPL", limit=3)
    assert len(result) == 3


def test_merge_attaches_ticker():
    a = _article("http://example.com/1", "2024-01-01T00:00:00")
    result = merge([a], [], ticker="TSLA")
    assert result[0].ticker == "TSLA"


def test_merge_empty_sources_returns_empty():
    assert merge([], [], ticker="AAPL") == []


def test_merge_returns_newsitem_with_all_fields():
    a = _article("http://example.com/1", "2024-01-01T00:00:00", sentiment="positive")
    result = merge([a], [], ticker="AAPL")
    item = result[0]
    assert item.title == "Title http://example.com/1"
    assert item.source == "TestSource"
    assert item.url == "http://example.com/1"
    assert item.summary == "A summary."
    assert item.sentiment == "positive"
    assert item.ticker == "AAPL"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_aggregator.py -v
```

Expected: `ModuleNotFoundError: No module named 'news.aggregator'`

- [ ] **Step 3: Implement `news/aggregator.py`**

```python
from datetime import datetime, timezone

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
    limit: int = 10,
) -> list[NewsItem]:
    seen: set[str] = set()
    combined: list[RawArticle] = []
    for article in av_articles + fh_articles:
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
        )
        for a in combined[:limit]
    ]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_aggregator.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add news/aggregator.py tests/test_aggregator.py
git commit -m "feat: add aggregator with merge, dedup, sort, and top-N"
```

---

### Task 4: Sentiment mapping (TDD)

**Files:**
- Create: `tests/test_sentiment.py`
- Create stubs in: `news/alphavantage.py`, `news/finnhub.py`

**Interfaces:**
- Produces:
  - `news.alphavantage.map_av_sentiment(label: str) -> str`
  - `news.finnhub.map_fh_sentiment(score: float) -> str`

- [ ] **Step 1: Write failing sentiment tests**

Create `tests/test_sentiment.py`:

```python
from news.alphavantage import map_av_sentiment
from news.finnhub import map_fh_sentiment


# Alpha Vantage sentiment mapping
def test_av_bullish_is_positive():
    assert map_av_sentiment("Bullish") == "positive"


def test_av_somewhat_bullish_is_positive():
    assert map_av_sentiment("Somewhat-Bullish") == "positive"


def test_av_bearish_is_negative():
    assert map_av_sentiment("Bearish") == "negative"


def test_av_somewhat_bearish_is_negative():
    assert map_av_sentiment("Somewhat-Bearish") == "negative"


def test_av_neutral_is_neutral():
    assert map_av_sentiment("Neutral") == "neutral"


def test_av_unknown_label_is_neutral():
    assert map_av_sentiment("") == "neutral"
    assert map_av_sentiment("Unknown") == "neutral"


# Finnhub sentiment mapping (score-based)
def test_fh_positive_score_is_positive():
    assert map_fh_sentiment(0.5) == "positive"
    assert map_fh_sentiment(0.01) == "positive"


def test_fh_negative_score_is_negative():
    assert map_fh_sentiment(-0.3) == "negative"
    assert map_fh_sentiment(-0.01) == "negative"


def test_fh_zero_score_is_neutral():
    assert map_fh_sentiment(0.0) == "neutral"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_sentiment.py -v
```

Expected: `ModuleNotFoundError: No module named 'news.alphavantage'`

- [ ] **Step 3: Create `news/alphavantage.py` with mapping function**

```python
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
    matches = r.json().get("bestMatches", [])
    if not matches:
        return None
    return matches[0]["1. symbol"]


async def fetch_news(ticker: str) -> list[RawArticle]:
    """Fetch news articles with sentiment from Alpha Vantage NEWS_SENTIMENT endpoint."""
    api_key = os.environ["ALPHAVANTAGE_API_KEY"]
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(_AV_BASE, params={
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "apikey": api_key,
        })
        r.raise_for_status()
    return [
        RawArticle(
            title=item.get("title", ""),
            source=item.get("source", ""),
            published_at=_parse_av_date(item.get("time_published", "")),
            url=item.get("url", ""),
            summary=item.get("summary", ""),
            sentiment=map_av_sentiment(item.get("overall_sentiment_label", "")),
        )
        for item in r.json().get("feed", [])
    ]
```

- [ ] **Step 4: Create `news/finnhub.py` with mapping function**

```python
import os
from datetime import datetime, timezone

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
    from_date = today.replace(day=today.day - 7).strftime("%Y-%m-%d") if today.day > 7 else (
        today.replace(month=today.month - 1, day=today.day + 23).strftime("%Y-%m-%d")
    )
    to_date = today.strftime("%Y-%m-%d")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{_FH_BASE}/company-news", params={
            "symbol": ticker,
            "from": from_date,
            "to": to_date,
            "token": api_key,
        })
        r.raise_for_status()
    return [
        RawArticle(
            title=item.get("headline", ""),
            source=item.get("source", ""),
            published_at=_unix_to_iso(item.get("datetime", 0)),
            url=item.get("url", ""),
            summary=item.get("summary", ""),
            sentiment="neutral",  # free tier has no per-article sentiment
        )
        for item in r.json()
        if isinstance(r.json(), list)
    ]
```

- [ ] **Step 5: Run sentiment tests to confirm they pass**

```bash
uv run pytest tests/test_sentiment.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add news/alphavantage.py news/finnhub.py tests/test_sentiment.py
git commit -m "feat: add AV and Finnhub clients with sentiment mapping"
```

---

### Task 5: Fix Finnhub date calculation and run all unit tests

The date arithmetic in `fetch_news` is fragile. Replace with `timedelta`:

**Files:**
- Modify: `news/finnhub.py`

- [ ] **Step 1: Fix date calculation in `news/finnhub.py`**

Replace the `fetch_news` function body with:

```python
async def fetch_news(ticker: str) -> list[RawArticle]:
    """Fetch company news from Finnhub (last 7 days). Sentiment defaults to neutral
    since per-article sentiment is not available on the free tier."""
    api_key = os.environ["FINNHUB_API_KEY"]
    from datetime import timedelta
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
```

- [ ] **Step 2: Run all unit tests**

```bash
uv run pytest tests/test_aggregator.py tests/test_sentiment.py -v
```

Expected: all 16 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add news/finnhub.py
git commit -m "fix: use timedelta for Finnhub date range calculation"
```

---

### Task 6: FastMCP server — main.py

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `symbol_search`, `fetch_news` from `news.alphavantage`; `fetch_news` from `news.finnhub`; `merge` from `news.aggregator`
- Produces: MCP tool `get_stock_news(query: str) -> dict`

- [ ] **Step 1: Replace `main.py`**

```python
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
```

- [ ] **Step 2: Verify the file is importable (catches syntax errors)**

```bash
uv run python -c "import main; print('OK')"
```

Expected: `RuntimeError: Missing required environment variable: ALPHAVANTAGE_API_KEY`
(This is correct — keys are not set in the dev shell yet. The error proves the import and key-check logic work.)

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add FastMCP get_stock_news tool with parallel AV+Finnhub fetch"
```

---

### Task 7: Integration tests

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Create `tests/test_integration.py`**

```python
import asyncio
import os

import pytest

from news.aggregator import merge
from news.alphavantage import fetch_news as av_fetch_news
from news.alphavantage import symbol_search
from news.finnhub import fetch_news as fh_fetch_news
from news.models import NewsItem

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


async def test_symbol_search_resolves_company_name():
    ticker = await symbol_search("Apple")
    assert ticker == "AAPL"


async def test_av_fetch_news_returns_articles_with_sentiment():
    articles = await av_fetch_news("AAPL")
    assert len(articles) > 0
    for a in articles:
        assert a.title
        assert a.url
        assert a.sentiment in ("positive", "negative", "neutral")


async def test_fh_fetch_news_returns_list():
    articles = await fh_fetch_news("AAPL")
    assert isinstance(articles, list)
    for a in articles:
        assert a.sentiment in ("positive", "negative", "neutral")
        assert a.url


async def test_full_pipeline_returns_top_10():
    ticker = await symbol_search("Apple")
    assert ticker
    av_articles, fh_articles = await asyncio.gather(
        av_fetch_news(ticker),
        fh_fetch_news(ticker),
    )
    news = merge(av_articles, fh_articles, ticker)
    assert 0 < len(news) <= 10
    for item in news:
        assert isinstance(item, NewsItem)
        assert item.ticker == ticker
        assert item.url
        assert item.title
        assert item.sentiment in ("positive", "negative", "neutral")
```

- [ ] **Step 2: Confirm integration tests are skipped without the flag**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: all 4 tests SKIPPED with message `Set RUN_INTEGRATION_TESTS=1 to run integration tests`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests behind RUN_INTEGRATION_TESTS flag"
```

---

### Task 8: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen --no-cache

COPY main.py ./
COPY news/ ./news/

ENV PORT=8080

CMD ["uv", "run", "--no-dev", "python", "main.py"]
```

- [ ] **Step 2: Build the image locally to verify**

```bash
docker build -t stock-news-mcp .
```

Expected: image builds successfully.

- [ ] **Step 3: Smoke-test the container (requires API keys)**

```bash
docker run --rm \
  -e ALPHAVANTAGE_API_KEY=your_key \
  -e FINNHUB_API_KEY=your_key \
  -p 8080:8080 \
  stock-news-mcp
```

Expected: server starts and logs that it's listening on port 8080.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile for Cloud Run deployment"
```

---

## Running integration tests

To run against the real APIs:

```bash
ALPHAVANTAGE_API_KEY=your_key \
FINNHUB_API_KEY=your_key \
RUN_INTEGRATION_TESTS=1 \
uv run pytest tests/test_integration.py -v
```

## Running the server locally

```bash
ALPHAVANTAGE_API_KEY=your_key \
FINNHUB_API_KEY=your_key \
uv run python main.py
```

The MCP endpoint will be available at `http://localhost:8080/mcp`.
