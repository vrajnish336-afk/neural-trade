import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, MarketIntelligence, SentimentResult
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.decision.models import TraderDecision
from app.risk.engine import RiskEngine, RiskDecision
from app.strategies.ensemble import StrategyEnsemble
from app.services.intelligence import IntelligenceService
from app.forecasting.service import ForecastingService

@pytest.fixture
def dummy_bars():
    return [
        MarketBar(
            symbol="BTC/USD",
            timestamp=datetime(2023, 1, 1, 12, i, tzinfo=timezone.utc),
            open=100.0 + i,
            high=105.0 + i,
            low=95.0 + i,
            close=102.0 + i,
            volume=1000.0
        )
        for i in range(11)
    ]

@pytest.fixture
def mock_ensemble():
    return Mock(spec=StrategyEnsemble)

@pytest.fixture
def mock_risk_engine():
    return Mock(spec=RiskEngine)

@pytest.fixture
def mock_intelligence_service():
    return Mock(spec=IntelligenceService)

@pytest.fixture
def mock_forecasting_service():
    return Mock(spec=ForecastingService)

@pytest.fixture
def orchestrator(mock_ensemble, mock_risk_engine, mock_intelligence_service, mock_forecasting_service):
    return DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk_engine,
        intelligence_service=mock_intelligence_service,
        forecasting_service=mock_forecasting_service
    )

def test_decision_no_bars(orchestrator):
    decision = orchestrator.evaluate("BTC/USD", [], 10000.0, 0, 0.0)
    assert decision.decision == "NO TRADE"
    assert decision.data_freshness == "INSUFFICIENT"
    assert not decision.risk_gate_approved

def test_decision_no_signal(orchestrator, dummy_bars):
    orchestrator.intelligence_service.generate_intelligence.return_value = None
    orchestrator.ensemble.evaluate.return_value = None
    
    decision = orchestrator.evaluate("BTC/USD", dummy_bars, 10000.0, 0, 0.0)
    assert decision.decision == "NO TRADE"
    assert not decision.risk_gate_approved

def test_decision_long_approved(orchestrator, dummy_bars):
    # Setup Intelligence
    intel = MarketIntelligence(
        symbol="BTC/USD",
        timestamp=dummy_bars[-1].timestamp,
        sentiment=SentimentResult(score=0.8, label="POSITIVE", confidence=0.9, source_count=5, timestamp=dummy_bars[-1].timestamp),
        relevant_articles=5,
        anomaly_status=[],
        risk_flags=[],
        fakeout_risk="UNKNOWN"
    )
    orchestrator.intelligence_service.generate_intelligence.return_value = intel
    
    # Setup Signal
    signal = TradingSignal(
        symbol="BTC/USD",
        timestamp=dummy_bars[-1].timestamp,
        direction="LONG",
        strategy="TestStrategy",
        confidence=0.9,
        reason="Test breakout"
    )
    orchestrator.ensemble.evaluate.return_value = signal
    
    # Setup Risk
    risk_dec = RiskDecision(
        approved=True,
        requested_risk=100.0,
        allowed_risk=100.0,
        position_size=1.0
    )
    orchestrator.risk_engine.evaluate_trade.return_value = risk_dec
    
    # Setup Forecast
    mock_forecast = Mock()
    mock_forecast.predicted_values_json = "[120.0, 125.0]"
    orchestrator.forecasting_service.generate_forecast.return_value = mock_forecast
    
    decision = orchestrator.evaluate("BTC/USD", dummy_bars, 10000.0, 0, 0.0)
    
    assert decision.decision == "LONG"
    assert decision.risk_gate_approved is True
    assert decision.paper_execution_eligible is True
    assert decision.forecast_direction == "UP"
    assert decision.world_context == "POSITIVE"

def test_decision_risk_rejected(orchestrator, dummy_bars):
    # Setup Signal
    signal = TradingSignal(
        symbol="BTC/USD",
        timestamp=dummy_bars[-1].timestamp,
        direction="SHORT",
        strategy="TestStrategy",
        confidence=0.9,
        reason="Test breakdown"
    )
    orchestrator.ensemble.evaluate.return_value = signal
    
    # Setup Risk Rejected
    risk_dec = RiskDecision(
        approved=False,
        requested_risk=100.0,
        allowed_risk=0.0,
        position_size=0.0,
        rejection_reason="Max positions reached",
        relevant_limit="Max positions"
    )
    orchestrator.risk_engine.evaluate_trade.return_value = risk_dec
    
    # Setup Intelligence to avoid Mock leaking into string
    intel = MarketIntelligence(
        symbol="BTC/USD",
        timestamp=dummy_bars[-1].timestamp,
        sentiment=SentimentResult(score=0.0, label="NEUTRAL", confidence=0.5, source_count=1, timestamp=dummy_bars[-1].timestamp),
        relevant_articles=0,
        anomaly_status=[],
        risk_flags=[],
        fakeout_risk="UNKNOWN"
    )
    orchestrator.intelligence_service.generate_intelligence.return_value = intel
    
    decision = orchestrator.evaluate("BTC/USD", dummy_bars, 10000.0, 5, 5000.0)
    
    # Decision must become WAIT if risk rejected
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert decision.paper_execution_eligible is False
    assert "Risk Gate" in decision.rationale

def test_decision_insufficient_data(orchestrator):
    decision = orchestrator.evaluate("BTC/USD", [], 10000.0, 0, 0.0)
    assert decision.decision == "NO TRADE"
    assert decision.data_freshness == "INSUFFICIENT"
    assert not decision.risk_gate_approved

def test_llm_unavailable_fallback(orchestrator, dummy_bars):
    # LLM might be used in copilot, but orchestrator should be deterministic and safe without it.
    orchestrator.intelligence_service.generate_intelligence.side_effect = Exception("LLM connection refused")
    orchestrator.ensemble.evaluate.return_value = None
    
    # Should not crash, should return NO TRADE due to exception hiding or handling
    decision = orchestrator.evaluate("BTC/USD", dummy_bars, 10000.0, 0, 0.0)
    assert decision.decision == "NO TRADE"
    assert decision.world_context == "UNKNOWN"
    assert not decision.risk_gate_approved
