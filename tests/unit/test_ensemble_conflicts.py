import pytest
from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, SignalScore
from app.strategies.ensemble import StrategyEnsemble
from app.diagnostics.models import RejectionReason

def test_ensemble_opposite_conflict_resolves_by_confidence():
    ensemble = StrategyEnsemble([])
    sig1 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="SHORT", strategy="Breakout", confidence=0.7, entry_price=100, reason="test")
    sig2 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="LONG", strategy="TF", confidence=0.8, entry_price=100, reason="test")
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)
    res = ensemble.evaluate([], regime, None, pre_generated_signals=[sig1, sig2])
    assert res is not None
    assert res.direction == "LONG"
    assert res.confidence == 0.8

def test_ensemble_trending_up_conflict_cannot_be_incorrectly_approved():
    ensemble = StrategyEnsemble([])
    sig1 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="SHORT", strategy="Breakout", confidence=0.9, entry_price=100, reason="test")
    sig2 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="LONG", strategy="TF", confidence=0.8, entry_price=100, reason="test")
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)
    res = ensemble.evaluate([], regime, None, pre_generated_signals=[sig1, sig2])
    assert res is None # Vetoed

def test_ensemble_trending_down_conflict_cannot_be_incorrectly_approved():
    ensemble = StrategyEnsemble([])
    sig1 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="SHORT", strategy="Breakout", confidence=0.7, entry_price=100, reason="test")
    sig2 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="LONG", strategy="TF", confidence=0.9, entry_price=100, reason="test")
    regime = MarketRegimeResult(regime="TRENDING_DOWN", confidence=1.0)
    res = ensemble.evaluate([], regime, None, pre_generated_signals=[sig1, sig2])
    assert res is None # Vetoed

def test_ensemble_genuine_tie_safely_vetoes():
    ensemble = StrategyEnsemble([])
    sig1 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="SHORT", strategy="Breakout", confidence=0.8, entry_price=100, reason="test")
    sig2 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="LONG", strategy="TF", confidence=0.8, entry_price=100, reason="test")
    regime = MarketRegimeResult(regime="RANGE_BOUND", confidence=1.0)
    res = ensemble.evaluate([], regime, None, pre_generated_signals=[sig1, sig2])
    assert res is None # Tie across different directions

def test_ensemble_normal_behavior_unchanged():
    ensemble = StrategyEnsemble([])
    sig1 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="LONG", strategy="S1", confidence=0.7, entry_price=100, reason="test")
    sig2 = TradingSignal(symbol="BTC", timestamp="2020-01-01", direction="LONG", strategy="S2", confidence=0.8, entry_price=100, reason="test")
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)
    res = ensemble.evaluate([], regime, None, pre_generated_signals=[sig1, sig2])
    assert res is not None
    assert res.direction == "LONG"
    assert "S1" in res.reason
    assert "S2" in res.strategy
