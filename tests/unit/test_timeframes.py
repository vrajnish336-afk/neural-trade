import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar
from app.analysis.timeframes import resample_bars

def test_timeframe_resampling():
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bars = []
    # Generate 60 1-minute bars
    for i in range(60):
        bars.append(MarketBar(
            symbol="BTC", timestamp=base_time + timedelta(minutes=i),
            open=100+i, high=105+i, low=95+i, close=102+i, volume=10
        ))
        
    # Resample to 1h
    df = resample_bars(bars, '1h')
    
    assert len(df) == 1
    # Check OHLC aggregated correctly
    assert df.iloc[0]['open'] == 100
    assert df.iloc[0]['high'] == 105 + 59
    assert df.iloc[0]['low'] == 95
    assert df.iloc[0]['close'] == 102 + 59
    assert df.iloc[0]['volume'] == 60 * 10
    
def test_incomplete_future_candle():
    # Only 15 minutes of data
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(15):
        bars.append(MarketBar(
            symbol="BTC", timestamp=base_time + timedelta(minutes=i),
            open=100, high=105, low=95, close=102, volume=10
        ))
        
    df = resample_bars(bars, '1h')
    # It will group into the 1h bucket starting at 2023-01-01 00:00:00
    assert len(df) == 1
    assert df.index[0] == base_time
