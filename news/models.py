from dataclasses import dataclass, asdict


@dataclass
class RawArticle:
    title: str
    source: str
    published_at: str  # ISO-8601 or AV format; normalised by each client
    url: str
    summary: str
    sentiment: str  # "positive" | "negative" | "neutral"
    source_api: str  # "alphavantage" | "finnhub"


@dataclass
class NewsItem:
    title: str
    source: str
    published_at: str
    url: str
    summary: str
    sentiment: str
    ticker: str
    source_api: str  # "alphavantage" | "finnhub"

    def to_dict(self) -> dict:
        return asdict(self)
