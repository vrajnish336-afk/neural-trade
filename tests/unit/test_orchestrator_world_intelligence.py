import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from app.core.models import MarketBar, TradingSignal, MarketIntelligence, SentimentResult
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.config import config

def test_world_intelligence_flag_disabled_baseline():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel_service = MagicMock()
    mock_forecast = MagicMock()
    mock_world_intel = MagicMock()
    
    mock_ensemble.evaluate.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    intel = MarketIntelligence(
        symbol="BTC/USD",
        timestamp=datetime.now(timezone.utc),
        sentiment=SentimentResult(score=0.5, label="POSITIVE", confidence=0.8, source_count=2, timestamp=datetime.now(timezone.utc)),
        relevant_articles=2,
        anomaly_status=[],
        risk_flags=[],
        fakeout_risk="LOW"
    )
    mock_intel_service.generate_intelligence.return_value = intel
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel_service,
        forecasting_service=mock_forecast,
        world_intelligence_service=mock_world_intel
    )
    
    now = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=99.0, close=102.0, volume=50.0)]
    
    with patch.object(config, "MACRO_INTELLIGENCE_ENABLED", False):
        decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
        
        # Verify WorldIntelligenceService was NOT called when flag is False
        mock_world_intel.aggregate_context.assert_not_called()
        assert decision.world_context == "POSITIVE"

def test_world_intelligence_flag_enabled_attaches_context():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel_service = MagicMock()
    mock_forecast = MagicMock()
    mock_world_intel = MagicMock()
    
    mock_ensemble.evaluate.return_value = None
    mock_intel_service.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    mock_ctx = MagicMock()
    mock_ctx.sentiment_summary = 0.75
    mock_world_intel.aggregate_context.return_value = mock_ctx
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel_service,
        forecasting_service=mock_forecast,
        world_intelligence_service=mock_world_intel
    )
    
    now = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=99.0, close=102.0, volume=50.0)]
    
    with patch.object(config, "MACRO_INTELLIGENCE_ENABLED", True):
        decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
        
        mock_world_intel.aggregate_context.assert_called_once()
        assert "Score:0.75" in decision.world_context

def test_world_intelligence_unavailable_fallback():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel_service = MagicMock()
    mock_forecast = MagicMock()
    mock_world_intel = MagicMock()
    
    mock_ensemble.evaluate.return_value = None
    mock_intel_service.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    mock_world_intel.aggregate_context.side_effect = Exception("API connection unavailable")
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel_service,
        forecasting_service=mock_forecast,
        world_intelligence_service=mock_world_intel
    )
    
    now = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=99.0, close=102.0, volume=50.0)]
    
    with patch.object(config, "MACRO_INTELLIGENCE_ENABLED", True):
        decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
        assert decision.world_context == "NOT_AVAILABLE"

def test_risk_engine_remains_authoritative_with_world_context():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel_service = MagicMock()
    mock_forecast = MagicMock()
    mock_world_intel = MagicMock()
    
    sig = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.9, reason="Strong buy", entry_price=100.0
    )
    mock_ensemble.evaluate.return_value = sig
    mock_intel_service.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    mock_ctx = MagicMock()
    mock_ctx.sentiment_summary = 0.95
    mock_world_intel.aggregate_context.return_value = mock_ctx
    
    # RiskEngine rejects trade
    mock_risk.evaluate_trade.return_value = MagicMock(approved=False, rejection_reason="Drawdown limit hit")
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel_service,
        forecasting_service=mock_forecast,
        world_intelligence_service=mock_world_intel
    )
    
    now = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=99.0, close=102.0, volume=50.0)]
    
    with patch.object(config, "MACRO_INTELLIGENCE_ENABLED", True):
        decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
        
        assert decision.decision == "WAIT"
        assert decision.risk_gate_approved is False
        assert decision.paper_execution_eligible is False
