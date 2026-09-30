import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.core.models import MarketBar, TradingSignal, MarketRegimeResult
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.weighting_engine import PerformanceWeightingEngine
from app.config import config

def test_ensemble_weighting_disabled_baseline_output():
    mock_strategy = MagicMock()
    sig = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, reason="Breakout detected", entry_price=100.0
    )
    mock_strategy.generate_signal.return_value = sig
    mock_strategy.__class__.__name__ = "BreakoutStrategy"
    
    ensemble = StrategyEnsemble(strategies=[mock_strategy])
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=0.9)
    
    with patch.object(config, "STRATEGY_WEIGHTING_ENABLED", False):
        result = ensemble.evaluate(bars=[], regime=regime, pre_generated_signals=[sig])
        assert result is not None
        assert result.confidence == 0.8

def test_ensemble_weighting_enabled_confidence_adjustment():
    mock_strategy = MagicMock()
    sig = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="TrendFollowingStrategy", confidence=0.5, reason="Trend signal", entry_price=100.0
    )
    mock_strategy.generate_signal.return_value = sig
    mock_strategy.__class__.__name__ = "TrendFollowingStrategy"
    
    mock_engine = MagicMock()
    mock_engine.calculate_weight.return_value = 1.5 # 1.5x weight
    
    ensemble = StrategyEnsemble(strategies=[mock_strategy], weighting_engine=mock_engine)
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=0.9)
    
    with patch.object(config, "STRATEGY_WEIGHTING_ENABLED", True):
        result = ensemble.evaluate(bars=[], regime=regime, pre_generated_signals=[sig], paper_trades=[{"realized_pnl": 100.0}])
        assert result is not None
        assert result.confidence == 0.75 # 0.5 * 1.5 = 0.75

def test_ensemble_weighting_clamped_bounds():
    sig = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="TrendFollowingStrategy", confidence=0.8, reason="Trend following", entry_price=100.0
    )
    mock_engine = MagicMock()
    mock_engine.calculate_weight.return_value = 2.0 # Upper bound
    
    ensemble = StrategyEnsemble(strategies=[], weighting_engine=mock_engine)
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=0.9)
    
    with patch.object(config, "STRATEGY_WEIGHTING_ENABLED", True):
        result = ensemble.evaluate(bars=[], regime=regime, pre_generated_signals=[sig])
        assert result is not None
        assert result.confidence <= 1.0 # Clamped to 1.0 max confidence

def test_risk_engine_overrides_weighted_signals():
    mock_risk = MagicMock()
    mock_risk.evaluate_trade.return_value = MagicMock(approved=False, rejection_reason="Drawdown limit hit")
    
    sig = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.95, reason="Strong buy", entry_price=100.0
    )
    
    from app.decision.decision_orchestrator import DecisionOrchestrator
    mock_ensemble = MagicMock()
    mock_ensemble.evaluate.return_value = sig
    mock_intel = MagicMock()
    mock_intel.generate_intelligence.return_value = None
    mock_forecast = MagicMock()
    mock_forecast.generate_forecast.return_value = None
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast
    )
    
    now = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=99.0, close=102.0, volume=50.0)]
    
    decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
    
    # RiskEngine vetoes trade execution regardless of high confidence
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert decision.paper_execution_eligible is False
