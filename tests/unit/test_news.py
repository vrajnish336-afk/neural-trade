import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import NewsArticle, SentimentResult
from app.news.sentiment import analyze_sentiment, is_article_relevant
from app.news.provider import FixtureNewsProvider
from app.news.aggregator import aggregate_sentiment

def test_sentiment_analysis():
    # Positive
    res = analyze_sentiment("The company saw a massive profit and strong growth", datetime.now(timezone.utc))
    assert res.label == "POSITIVE"
    assert res.score > 0
    
    # Negative
    res = analyze_sentiment("Massive loss and lawsuit after the recent crash", datetime.now(timezone.utc))
    assert res.label == "NEGATIVE"
    assert res.score < 0
    
    # Neutral/Empty
    res = analyze_sentiment("The company announced its Q3 report today", datetime.now(timezone.utc))
    assert res.label == "NEUTRAL"
    assert res.score == 0

def test_is_article_relevant():
    article = NewsArticle(
        id="1", timestamp=datetime.now(timezone.utc), source="test",
        title="Apple releases new phone", summary="AAPL stock jumps", symbols=["AAPL"]
    )
    assert is_article_relevant(article, "AAPL")
    assert is_article_relevant(article, "Apple", ["Apple"])
    assert not is_article_relevant(article, "MSFT")

def test_fixture_provider():
    now = datetime.now(timezone.utc)
    a1 = NewsArticle(id="1", timestamp=now, source="x", title="T1", summary="S1", symbols=["BTC"])
    a2 = NewsArticle(id="2", timestamp=now - timedelta(days=2), source="y", title="T2", summary="S2", symbols=["BTC"])
    a3 = NewsArticle(id="2", timestamp=now - timedelta(days=2), source="y", title="T2", summary="S2", symbols=["BTC"]) # Duplicate ID
    
    provider = FixtureNewsProvider(fixtures=[a1, a2, a3])
    
    # Range that only includes a1
    res = provider.get_articles("BTC", now - timedelta(hours=1), now + timedelta(hours=1))
    assert len(res) == 1
    assert res[0].id == "1"
    
    # Wide range should deduplicate a3
    res_all = provider.get_articles("BTC", now - timedelta(days=5), now + timedelta(hours=1))
    assert len(res_all) == 2

def test_aggregate_sentiment():
    now = datetime.now(timezone.utc)
    s1 = SentimentResult(score=1.0, label="POSITIVE", confidence=1.0, source_count=1, timestamp=now)
    s2 = SentimentResult(score=1.0, label="POSITIVE", confidence=1.0, source_count=1, timestamp=now)
    
    agg = aggregate_sentiment([s1, s2], now)
    assert agg.label == "POSITIVE"
    assert agg.source_count == 2
    
    assert aggregate_sentiment([], now) is None
