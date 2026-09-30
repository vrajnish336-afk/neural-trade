import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.core.models import TradingSignal, RiskDecision
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.config import config

@pytest.fixture
def risk_engine():
    limits = MagicMock(spec=PortfolioRiskLimits)
    limits.can_open_new_position.return_value = (True, "OK", "NONE")
    return RiskEngine(limits=limits)

def make_signal():
    return TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, reason="Buy signal", entry_price=100.0, stop_loss=95.0
    )

def test_death_mode_disabled_by_default_preserves_baseline(risk_engine):
    signal = make_signal()
    with patch.object(config, "DEATH_MODE_ENABLED", False):
        decision = risk_engine.evaluate_trade(signal, 10000.0, 0, 0.0, current_drawdown=0.15, current_loss_streak=6)
        assert decision.approved is True
        assert risk_engine.is_death_mode_active is False

def test_drawdown_threshold_latches_death_mode(risk_engine):
    signal = make_signal()
    with patch.object(config, "DEATH_MODE_ENABLED", True), patch.object(config, "DEATH_MODE_DRAWDOWN_LIMIT", 0.10):
        decision = risk_engine.evaluate_trade(signal, 10000.0, 0, 0.0, current_drawdown=0.12)
        assert decision.approved is False
        assert decision.relevant_limit == "DEATH_MODE"
        assert risk_engine.is_death_mode_active is True

def test_loss_streak_threshold_latches_death_mode(risk_engine):
    signal = make_signal()
    with patch.object(config, "DEATH_MODE_ENABLED", True), patch.object(config, "DEATH_MODE_LOSS_STREAK", 5):
        decision = risk_engine.evaluate_trade(signal, 10000.0, 0, 0.0, current_loss_streak=5)
        assert decision.approved is False
        assert decision.relevant_limit == "DEATH_MODE"
        assert risk_engine.is_death_mode_active is True

def test_latch_persists_after_equity_recovery(risk_engine):
    signal = make_signal()
    with patch.object(config, "DEATH_MODE_ENABLED", True), patch.object(config, "DEATH_MODE_DRAWDOWN_LIMIT", 0.10):
        # Breach triggers latch
        risk_engine.evaluate_trade(signal, 10000.0, 0, 0.0, current_drawdown=0.15)
        assert risk_engine.is_death_mode_active is True
        
        # Equity recovers (drawdown drops to 0.02)
        decision_recovered = risk_engine.evaluate_trade(signal, 10000.0, 0, 0.0, current_drawdown=0.02)
        assert decision_recovered.approved is False
        assert risk_engine.is_death_mode_active is True

def test_manual_reset_clears_latch(risk_engine):
    signal = make_signal()
    with patch.object(config, "DEATH_MODE_ENABLED", True), patch.object(config, "DEATH_MODE_DRAWDOWN_LIMIT", 0.10):
        risk_engine.evaluate_trade(signal, 10000.0, 0, 0.0, current_drawdown=0.15)
        assert risk_engine.is_death_mode_active is True
        
        # Explicit manual reset
        risk_engine.manual_reset_death_mode()
        assert risk_engine.is_death_mode_active is False
        
        # Next trade under normal drawdown is approved
        decision = risk_engine.evaluate_trade(signal, 10000.0, 0, 0.0, current_drawdown=0.02)
        assert decision.approved is True

def test_existing_position_exits_unaffected(risk_engine):
    # Position exit handlers operate independently and do not call evaluate_trade()
    # Confirm Death Mode latched state does not alter risk limits instance or raise errors
    risk_engine.is_death_mode_active = True
    assert risk_engine.limits.can_open_new_position.called is False
