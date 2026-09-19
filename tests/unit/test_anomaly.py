import pytest
from datetime import datetime, timezone
from app.core.models import MarketBar
from app.analysis.anomaly import detect_anomalies

def test_anomaly_insufficient_data():
    bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=2, low=1, close=1, volume=1)]
    assert "INSUFFICIENT_DATA" in detect_anomalies(bars, lookback=10)

def test_anomaly_unusual_volume():
    bars = []
    # 20 bars with alternating volume to create variance
    for i in range(20):
        vol = 1000 if i % 2 == 0 else 900
        bars.append(MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=100, high=105, low=95, close=100, volume=vol))
        
    # 1 anomalous bar
    bars.append(MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=100, high=105, low=95, close=100, volume=10000))
    
    flags = detect_anomalies(bars, zscore_threshold=2.0, lookback=20)
    assert "UNUSUAL_VOLUME" in flags
    assert "ABNORMAL_PRICE_MOVE" not in flags

def test_anomaly_abnormal_price_move():
    bars = []
    # 20 bars with alternating closes to create variance
    for i in range(20):
        close_price = 101 if i % 2 == 0 else 99
        bars.append(MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=100, high=105, low=95, close=close_price, volume=1000))
        
    # 1 anomalous bar
    bars.append(MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=101, high=150, low=99, close=150, volume=1000))
    
    flags = detect_anomalies(bars, zscore_threshold=2.0, lookback=20)
    assert "ABNORMAL_PRICE_MOVE" in flags
