import pytest
from datetime import datetime, timezone
from app.core.models import MarketBar
from app.analysis.fakeout import assess_breakout_quality

def generate_bars(closes, volumes):
    return [
        MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=c, high=c*1.05, low=c*0.95, close=c, volume=v)
        for c, v in zip(closes, volumes)
    ]

def test_fakeout_insufficient_data():
    bars = generate_bars([100], [1000])
    assert assess_breakout_quality(bars, "LONG", 100, lookback=14) == "INSUFFICIENT_DATA"

def test_fakeout_low_volume():
    # 15 bars, avg vol ~ 1000. Last bar vol is 500 (low)
    closes = [100]*14 + [102]
    volumes = [1000]*14 + [500]
    bars = generate_bars(closes, volumes)
    
    res = assess_breakout_quality(bars, "LONG", 101, lookback=14)
    assert res == "POSSIBLE_FAKEOUT"
    
def test_fakeout_exhaustion():
    # 15 bars. High volume, but price moves WAY too far past ATR.
    # Base ATR is around 100 * 0.10 = 10 (since high/low are +/- 5%)
    # Let's say entry was 101, close is 150. Distance = 49.
    closes = [100]*14 + [150]
    volumes = [1000]*14 + [2000] # High volume
    bars = generate_bars(closes, volumes)
    
    res = assess_breakout_quality(bars, "LONG", 101, lookback=14)
    assert res == "POSSIBLE_FAKEOUT"

def test_fakeout_high_quality():
    # Reasonable move, high volume
    closes = [100]*14 + [105]
    volumes = [1000]*14 + [2000] 
    bars = generate_bars(closes, volumes)
    
    res = assess_breakout_quality(bars, "LONG", 104, lookback=14)
    assert res == "HIGH_QUALITY"
