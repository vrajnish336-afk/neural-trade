import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar, TradingSignal
from app.backtesting.models import CostConfig
from app.research.multi_timeframe.models import TimeframeHierarchy
from app.research.multi_timeframe.validator import TimeframeValidator
from app.research.multi_timeframe.builder import MultiTimeframeContextBuilder
from app.research.multi_timeframe.service import MultiTimeframeService
from app.research.multi_timeframe.strategy import MultiTimeframeStrategy

def test_timeframe_validator():
    # Valid
    assert TimeframeValidator.validate_hierarchy(TimeframeHierarchy(higher_timeframe="1D", middle_timeframe="4H", lower_timeframe="1H"))
    assert TimeframeValidator.validate_hierarchy(TimeframeHierarchy(higher_timeframe="4H", middle_timeframe="1H", lower_timeframe="15m"))
    assert TimeframeValidator.validate_hierarchy(TimeframeHierarchy(higher_timeframe="1H", lower_timeframe="5m"))
    
    # Invalid (equal)
    assert not TimeframeValidator.validate_hierarchy(TimeframeHierarchy(higher_timeframe="1H", middle_timeframe="1H", lower_timeframe="15m"))
    # Invalid (reversed)
    assert not TimeframeValidator.validate_hierarchy(TimeframeHierarchy(higher_timeframe="15m", middle_timeframe="1H", lower_timeframe="4H"))
    # Invalid (unparseable)
    assert not TimeframeValidator.validate_hierarchy(TimeframeHierarchy(higher_timeframe="XYZ", lower_timeframe="5m"))

def test_context_builder_no_lookahead():
    hierarchy = TimeframeHierarchy(higher_timeframe="1H", lower_timeframe="15m")
    as_of = datetime(2025, 1, 1, tzinfo=timezone.utc)
    builder = MultiTimeframeContextBuilder(hierarchy, "test", as_of)
    
    # Generate 15m bars from 10:00 to 11:15
    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    bars = []
    for i in range(6): # 10:00, 10:15, 10:30, 10:45, 11:00, 11:15
        bars.append(MarketBar(
            symbol="BTC", timestamp=base_time + timedelta(minutes=15*i),
            open=100+i, high=105+i, low=95+i, close=102+i, volume=10
        ))
        
    # At 10:45, the 1H candle (10:00 - 11:00) is NOT complete.
    # Therefore, builder should return None for HTF because there is no completed 1H candle prior to 10:00 available?
    # Wait, pandas resample with closed='left' for '10:00' to '11:00' requires the time to cross 11:00.
    ctx_1045 = builder.build_context(bars[:4]) 
    assert ctx_1045 is None # No completed 1H candle exists in the slice yet (the 10:00 one is in progress)
    
    # At 11:00, the 1H candle for 10:00 is completed!
    # Because 11:00 >= 11:00. 
    ctx_1100 = builder.build_context(bars[:5])
    assert ctx_1100 is not None
    assert ctx_1100.htf_state.timeframe == "1h"
    assert ctx_1100.htf_state.timestamp == datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    
    # At 11:15, the 1H candle for 10:00 is still the most recently completed HTF candle.
    ctx_1115 = builder.build_context(bars)
    assert ctx_1115 is not None
    assert ctx_1115.htf_state.timestamp == datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

def test_ablation_service():
    service = MultiTimeframeService()
    hierarchy = TimeframeHierarchy(higher_timeframe="1H", lower_timeframe="15m")
    as_of = datetime(2025, 1, 1, tzinfo=timezone.utc)
    
    # Mock some data that forces a trade
    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    bars = []
    # Create enough bars so that a 1H candle completes and we get a signal
    for i in range(10): 
        bars.append(MarketBar(
            symbol="BTC", timestamp=base_time + timedelta(minutes=15*i),
            open=100+i, high=105+i, low=95+i, close=102+i, volume=10
        ))
        
    # HTF logic: Always True
    def htf_logic(ctx, h_bars): return True
    # MTF logic: Not used in this hierarchy
    def mtf_logic(ctx, h_bars): return True
    # LTF logic: Buy on the very first bar it evaluates successfully
    def ltf_logic(ctx, h_bars):
        return TradingSignal(
            symbol="BTC", direction="LONG", timestamp=h_bars[-1].timestamp,
            entry_price=h_bars[-1].close, stop_loss=h_bars[-1].close - 10, take_profit=h_bars[-1].close + 20
        )
        
    res = service.evaluate_ablation(
        candidate_id="cand_1", hierarchy=hierarchy, bars=bars,
        htf_logic=htf_logic, mtf_logic=mtf_logic, ltf_logic=ltf_logic,
        cost_config=CostConfig(commission_rate=0.0, slippage_rate=0.0), as_of=as_of
    )
    
    # The ablation should complete successfully.
    assert res.baseline_return_pct is not None
    assert res.full_return_pct is not None
