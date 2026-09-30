import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, RiskDecision
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.config import config

@pytest.fixture
def dummy_dependencies():
    ensemble = MagicMock()
    risk_engine = MagicMock()
    risk_engine.evaluate_trade.return_value = RiskDecision(
        approved=True, requested_risk=100.0, allowed_risk=100.0, position_size=1.0
    )
    intelligence_service = MagicMock()
    intelligence_mock = MagicMock()
    intelligence_mock.sentiment.label = "NEUTRAL"
    intelligence_service.generate_intelligence.return_value = intelligence_mock
    
    forecasting_service = MagicMock()
    
    return {
        "ensemble": ensemble,
        "risk_engine": risk_engine,
        "intelligence_service": intelligence_service,
        "forecasting_service": forecasting_service,
    }

def create_bar(close_price: float):
    return MarketBar(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc),
        open=close_price, high=close_price, low=close_price, close=close_price, volume=10.0
    )

@patch('app.analysis.regime.detect_market_regime')
def test_price_below_threshold_no_breaker(mock_detect, dummy_dependencies):
    orchestrator = DecisionOrchestrator(**dummy_dependencies)
    bars = [create_bar(99000.0)]
    
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, entry_price=99000.0, reason="test"
    )
    dummy_dependencies["ensemble"].evaluate.return_value = signal
    
    # Mock detect_market_regime
    mock_detect.return_value = MarketRegimeResult(regime="HIGH_VOLATILITY", confidence=0.9)
    
    config.CIRCUIT_BREAKER_PRICE_THRESHOLD = 100000.0
    
    decision = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    assert decision.decision == "LONG"
    assert "Circuit Breaker Active" not in decision.rationale

@patch('app.analysis.regime.detect_market_regime')
def test_price_above_threshold_extreme_volatility_breaker(mock_detect, dummy_dependencies):
    orchestrator = DecisionOrchestrator(**dummy_dependencies)
    bars = [create_bar(105000.0)]
    
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, entry_price=105000.0, reason="test"
    )
    dummy_dependencies["ensemble"].evaluate.return_value = signal
    
    mock_detect.return_value = MarketRegimeResult(regime="HIGH_VOLATILITY", confidence=0.9)
    
    config.CIRCUIT_BREAKER_PRICE_THRESHOLD = 100000.0
    
    decision = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    assert decision.decision == "WAIT"
    assert "Circuit Breaker" in decision.rationale
    assert "Blow-Off-Top" in decision.rationale

@patch('app.analysis.regime.detect_market_regime')
def test_price_above_threshold_normal_volatility_no_breaker(mock_detect, dummy_dependencies):
    orchestrator = DecisionOrchestrator(**dummy_dependencies)
    bars = [create_bar(105000.0)]
    
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, entry_price=105000.0, reason="test"
    )
    dummy_dependencies["ensemble"].evaluate.return_value = signal
    
    mock_detect.return_value = MarketRegimeResult(regime="TRENDING_UP", confidence=0.9)
    
    config.CIRCUIT_BREAKER_PRICE_THRESHOLD = 100000.0
    
    decision = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    assert decision.decision == "LONG"
    assert "Circuit Breaker" not in decision.rationale

@patch('app.analysis.regime.detect_market_regime')
def test_missing_volatility_fails_closed(mock_detect, dummy_dependencies):
    orchestrator = DecisionOrchestrator(**dummy_dependencies)
    bars = [create_bar(105000.0)]
    
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, entry_price=105000.0, reason="test"
    )
    dummy_dependencies["ensemble"].evaluate.return_value = signal
    
    mock_detect.return_value = MarketRegimeResult(regime="INSUFFICIENT_DATA", confidence=0.0)
    
    config.CIRCUIT_BREAKER_PRICE_THRESHOLD = 100000.0
    
    decision = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    assert decision.decision == "WAIT"
    assert "Circuit Breaker" in decision.rationale
    assert "Missing" in decision.rationale

@patch('app.analysis.regime.detect_market_regime')
def test_trend_following_unchanged(mock_detect, dummy_dependencies):
    orchestrator = DecisionOrchestrator(**dummy_dependencies)
    bars = [create_bar(105000.0)]
    
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="TrendFollowingStrategy", confidence=0.8, entry_price=105000.0, reason="test"
    )
    dummy_dependencies["ensemble"].evaluate.return_value = signal
    
    mock_detect.return_value = MarketRegimeResult(regime="HIGH_VOLATILITY", confidence=0.9)
    
    config.CIRCUIT_BREAKER_PRICE_THRESHOLD = 100000.0
    
    decision = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    # TrendFollowing should bypass the circuit breaker
    assert decision.decision == "LONG"
    assert "Circuit Breaker" not in decision.rationale

@patch('app.analysis.regime.detect_market_regime')
def test_no_existing_positions_force_closed(mock_detect, dummy_dependencies):
    # Testing that evaluate only yields "WAIT" which suppresses ENTRY.
    # It does not actively close existing positions.
    orchestrator = DecisionOrchestrator(**dummy_dependencies)
    bars = [create_bar(105000.0)]
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, entry_price=105000.0, reason="test"
    )
    dummy_dependencies["ensemble"].evaluate.return_value = signal
    mock_detect.return_value = MarketRegimeResult(regime="HIGH_VOLATILITY", confidence=0.9)
    config.CIRCUIT_BREAKER_PRICE_THRESHOLD = 100000.0
    
    decision = orchestrator.evaluate("BTC/USD", bars, 10000.0, 1, 0.5) # existing positions
    assert decision.decision == "WAIT" # Just waits.
