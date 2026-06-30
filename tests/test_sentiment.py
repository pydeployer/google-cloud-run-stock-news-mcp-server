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
