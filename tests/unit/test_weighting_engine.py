import pytest
from unittest.mock import patch
from app.strategies.weighting_engine import PerformanceWeightingEngine
from app.config import config

def test_weighting_disabled_returns_baseline():
    engine = PerformanceWeightingEngine()
    trades = [{"realized_pnl": 100.0} for _ in range(15)]
    
    with patch.object(config, "STRATEGY_WEIGHTING_ENABLED", False):
        weight = engine.calculate_weight("TrendFollowing", trades)
        assert weight == 1.0

def test_insufficient_sample_size_returns_baseline():
    engine = PerformanceWeightingEngine(min_sample_size=10)
    trades = [{"realized_pnl": 100.0} for _ in range(5)] # n = 5 < 10
    
    with patch.object(config, "STRATEGY_WEIGHTING_ENABLED", True):
        weight = engine.calculate_weight("TrendFollowing", trades)
        assert weight == 1.0

def test_ema_smoothing_and_clamping():
    engine = PerformanceWeightingEngine(min_sample_size=10, alpha=0.1, min_weight=0.5, max_weight=2.0)
    
    # 10 winning trades (100% win rate)
    winning_trades = [{"realized_pnl": 100.0} for _ in range(10)]
    
    with patch.object(config, "STRATEGY_WEIGHTING_ENABLED", True):
        # First iteration starting at prev_weight = 1.0
        # raw_multiplier > 1.0; EMA should gently increase weight above 1.0
        w1 = engine.calculate_weight("TrendFollowing", winning_trades, previous_weight=1.0)
        assert w1 > 1.0
        assert w1 <= 2.0
        
        # Test extreme upper clamping with huge positive score
        w_extreme = engine.calculate_weight("TrendFollowing", winning_trades, previous_weight=5.0)
        assert w_extreme <= 2.0
        
        # Test extreme lower clamping with losing trades
        losing_trades = [{"realized_pnl": -500.0} for _ in range(10)]
        w_low = engine.calculate_weight("TrendFollowing", losing_trades, previous_weight=0.1)
        assert w_low >= 0.5

def test_deterministic_bounded_output():
    engine = PerformanceWeightingEngine(min_sample_size=10)
    trades = [{"realized_pnl": 50.0 if i % 2 == 0 else -30.0} for i in range(12)]
    
    with patch.object(config, "STRATEGY_WEIGHTING_ENABLED", True):
        w_a = engine.calculate_weight("Breakout", trades, previous_weight=1.0)
        w_b = engine.calculate_weight("Breakout", trades, previous_weight=1.0)
        
        # Deterministic: identical inputs yield identical outputs
        assert w_a == w_b
        assert 0.5 <= w_a <= 2.0
