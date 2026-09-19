import pytest
from datetime import datetime, timezone
from app.core.models import MarketBar
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.mean_reversion import MeanReversionStrategy

def generate_bars(closes, volumes=None):
    volumes = volumes or [1000] * len(closes)
    return [
        MarketBar(
            symbol="BTC", 
            timestamp=datetime(2023, 1, i+1, tzinfo=timezone.utc), 
            open=c, high=c+1, low=c-1, close=c, volume=v
        ) for i, (c, v) in enumerate(zip(closes, volumes))
    ]

def test_trend_following_signal():
    strategy = TrendFollowingStrategy(fast_period=2, slow_period=3)
    closes = [10] * 15 + [10, 10, 10, 20]
    bars = generate_bars(closes)
    signal = strategy.generate_signal(bars)
    assert signal is not None

def test_trend_following_no_signal():
    strategy = TrendFollowingStrategy(fast_period=2, slow_period=3)
    closes = [10] * 20
    bars = generate_bars(closes)
    signal = strategy.generate_signal(bars)
    assert signal is None 

def test_breakout_signal():
    strategy = BreakoutStrategy(lookback_period=3, volume_period=3)
    closes = [10] * 15 + [10, 12, 11, 15] 
    volumes = [100] * 15 + [100, 100, 100, 200]
    bars = generate_bars(closes, volumes)
    signal = strategy.generate_signal(bars)
    assert signal is not None
    assert signal.direction == "LONG"

def test_mean_reversion_signal():
    strategy = MeanReversionStrategy(sma_period=3, deviation_multiplier=1.0)
    closes = [10] * 15 + [10, 10, 10, 20]
    bars = generate_bars(closes)
    signal = strategy.generate_signal(bars)
    assert signal is not None
    assert signal.direction == "SHORT"
