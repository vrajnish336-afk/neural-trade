import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar
from app.analysis.regime import detect_market_regime

def test_detect_insufficient_data():
    bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=2, low=1, close=1, volume=1)]
    result = detect_market_regime(bars)
    assert result.regime == "INSUFFICIENT_DATA"

def test_detect_trending_up():
    bars = []
    base_time = datetime(2023,1,1, tzinfo=timezone.utc)
    price = 100.0
    for i in range(120):
        bars.append(MarketBar(symbol="BTC", timestamp=base_time+timedelta(days=i), open=price, high=price+1, low=price-1, close=price+0.5, volume=100))
        price += 1.0 # Upward drift
        
    result = detect_market_regime(bars, lookback=20, atr_period=14)
    # With strict slope, should be trending up
    assert result.regime == "TRENDING_UP"

def test_detect_high_volatility():
    bars = []
    base_time = datetime(2023,1,1, tzinfo=timezone.utc)
    price = 100.0
    for i in range(120):
        if i < 100:
            # Normal vol
            bars.append(MarketBar(symbol="BTC", timestamp=base_time+timedelta(days=i), open=price, high=price+1, low=price-1, close=price, volume=100))
        else:
            # Huge swings
            close_val = 100.0 if i % 2 == 0 else 150.0
            bars.append(MarketBar(symbol="BTC", timestamp=base_time+timedelta(days=i), open=100, high=200, low=50, close=close_val, volume=100))
        
    result = detect_market_regime(bars)
    assert result.regime == "HIGH_VOLATILITY"
