import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.core.models import MarketBar, TradingSignal, RiskDecision
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.config import config

def test_orchestrator_death_mode_active_rationale_visible():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    
    sig = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.85, reason="Buy signal", entry_price=100.0, stop_loss=95.0
    )
    mock_ensemble.evaluate.return_value = sig
    mock_intel.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    # RiskEngine returns Death Mode rejection
    mock_risk.evaluate_trade.return_value = RiskDecision(
        approved=False, requested_risk=0.0, allowed_risk=0.0, position_size=0.0,
        rejection_reason="Rejected: Death Mode Active (Drawdown 15.00% >= limit 10.00%)",
        relevant_limit="DEATH_MODE"
    )
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast
    )
    
    now = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=99.0, close=102.0, volume=50.0)]
    
    with patch.object(config, "DEATH_MODE_ENABLED", True):
        decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
        
        assert decision.decision == "WAIT"
        assert "Death Mode Gate" in decision.rationale
        assert "Risk-Off Death Mode Halt (New Entries Blocked)" in decision.main_risks
        assert decision.risk_gate_approved is False

def test_orchestrator_death_mode_inactive_baseline_preserved():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    
    sig = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.85, reason="Buy signal", entry_price=100.0, stop_loss=95.0
    )
    mock_ensemble.evaluate.return_value = sig
    mock_intel.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    mock_risk.evaluate_trade.return_value = RiskDecision(
        approved=True, requested_risk=100.0, allowed_risk=100.0, position_size=1.0,
        rejection_reason=None, relevant_limit=None
    )
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast
    )
    
    now = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=99.0, close=102.0, volume=50.0)]
    
    with patch.object(config, "DEATH_MODE_ENABLED", False):
        decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
        
        assert decision.decision == "LONG"
        assert decision.risk_gate_approved is True
        assert "Death Mode Gate" not in decision.rationale
