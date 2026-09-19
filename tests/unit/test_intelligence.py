import pytest
from datetime import datetime, timezone
from app.services.intelligence import IntelligenceService
from app.news.provider import FixtureNewsProvider
from app.core.models import NewsArticle, MarketBar
from app.config import config

def test_intelligence_fusion():
    # Setup mock provider with positive news
    article = NewsArticle(
        id="1", timestamp=datetime.now(timezone.utc), source="test",
        title="Great profit and growth for BTC", summary="", symbols=["BTC"]
    )
    provider = FixtureNewsProvider([article])
    service = IntelligenceService(provider, config)
    
    bars = []
    for i in range(25):
        vol = 1000 if i % 2 == 0 else 900
        close = 100 if i % 2 == 0 else 101
        bars.append(MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=100, high=105, low=95, close=close, volume=vol))
        
    res = service.generate_intelligence("BTC", datetime.now(timezone.utc), bars, None)
    
    assert res.sentiment.label == "POSITIVE"
    assert res.relevant_articles == 1
    assert "UNUSUAL_VOLUME" not in res.anomaly_status
    assert res.fakeout_risk == "UNKNOWN" # No signal provided
