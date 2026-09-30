import pytest
from datetime import datetime, timedelta, timezone
from app.core.models import MarketBar
from app.analysis.mtf_engine import MultiTimeframeEngine, MultiTimeframeContext

def generate_bars(count: int, start_time: datetime, step_hours: int = 1, base_price: float = 100.0, trend_up: bool = True) -> list[MarketBar]:
    bars = []
    current = base_price
    for i in range(count):
        ts = start_time + timedelta(hours=i * step_hours)
        if trend_up:
            current += 1.0
        else:
            current -= 1.0
        bars.append(MarketBar(
            symbol="BTC/USD",
            timestamp=ts,
            open=current - 0.5,
            high=current + 1.0,
            low=current - 1.0,
            close=current,
            volume=100.0
        ))
    return bars

def test_mtf_engine_utc_normalization():
    engine = MultiTimeframeEngine()
    naive_dt = datetime(2026, 9, 20, 12, 0, 0)
    utc_dt = engine._ensure_utc(naive_dt)
    assert utc_dt.tzinfo == timezone.utc
    assert utc_dt.hour == 12

def test_mtf_engine_as_of_filtering_prevents_future_bars():
    engine = MultiTimeframeEngine()
    start = datetime(2026, 9, 20, 0, 0, 0, tzinfo=timezone.utc)
    all_h1 = generate_bars(60, start, step_hours=1, trend_up=True)
    
    # Evaluate decision at bar index 30
    eval_ts = all_h1[30].timestamp
    
    # Provide all 60 bars (30 of which are in the future relative to eval_ts)
    context = engine.align_timeframes("BTC/USD", eval_ts, h1_bars=all_h1)
    
    # The context timestamp must equal eval_ts and context must be fresh
    assert context.as_of_timestamp == eval_ts
    assert context.is_fresh is True
    assert context.alignment in ("ALIGNED_BULLISH", "NEUTRAL")

def test_mtf_engine_missing_data_fallback():
    engine = MultiTimeframeEngine()
    now = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    
    # Empty bars
    context = engine.align_timeframes("BTC/USD", now, h1_bars=[])
    assert context.alignment == "INSUFFICIENT_DATA"
    assert context.is_fresh is False

def test_mtf_engine_multi_timeframe_alignment():
    engine = MultiTimeframeEngine()
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    h1_bars = generate_bars(60, start, step_hours=1, base_price=100.0, trend_up=True)
    h4_bars = generate_bars(30, start, step_hours=4, base_price=100.0, trend_up=True)
    d1_bars = generate_bars(30, start, step_hours=24, base_price=100.0, trend_up=True)
    
    eval_ts = h1_bars[-1].timestamp
    context = engine.align_timeframes("BTC/USD", eval_ts, h1_bars=h1_bars, h4_bars=h4_bars, d1_bars=d1_bars)
    
    assert context.alignment == "ALIGNED_BULLISH"
    assert context.h1_trend == "BULLISH"
