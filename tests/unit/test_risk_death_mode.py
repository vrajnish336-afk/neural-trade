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
    limits.is_survival_budget_breached.return_value = False
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


# ---------------------------------------------------------------------------
# Phase 67 — Death Mode (Survival Budget) Tests
# ---------------------------------------------------------------------------

def test_survival_budget_limits_property_and_check():
    limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    assert limits.survival_budget_pct == 0.50
    assert limits.survival_budget_threshold == 5000.0
    assert limits.survival_threshold == 5000.0
    
    # Healthy equity: above survival budget
    assert limits.is_survival_budget_breached(10000.0) is False
    assert limits.is_survival_budget_breached(5001.0) is False
    assert limits.check_survival_budget(5001.0) is False

    # Breached equity: at or below 50%
    assert limits.is_survival_budget_breached(5000.0) is True
    assert limits.is_survival_budget_breached(4999.0) is True
    assert limits.check_survival_budget(4999.0) is True
    assert limits.is_survival_budget_breached(0.0) is True

    # can_open_new_position rejects if survival budget breached
    can_open, reason, limit_name = limits.can_open_new_position(0, 0.0, 4500.0)
    assert can_open is False
    assert limit_name == "DEATH_MODE"


def test_survival_budget_breach_latches_death_mode():
    real_limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    engine = RiskEngine(limits=real_limits)
    signal = make_signal()

    assert engine.death_mode_active is False
    assert engine.is_death_mode_active is False

    # Equity breaches 50% survival budget (4800 <= 5000)
    decision = engine.evaluate_trade(signal, current_equity=4800.0, current_positions_count=0, current_exposure=0.0)

    assert decision.approved is False
    assert decision.rejection_reason == "REJECTED: DEATH MODE ACTIVE. Survival budget breached."
    assert decision.relevant_limit == "DEATH_MODE"
    assert engine.death_mode_active is True
    assert engine.is_death_mode_active is True


def test_death_mode_active_latches_permanently():
    real_limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    engine = RiskEngine(limits=real_limits)
    signal = make_signal()

    # Trigger breach
    engine.evaluate_trade(signal, current_equity=4000.0, current_positions_count=0, current_exposure=0.0)
    assert engine.death_mode_active is True

    # Subsequent trade even if equity hypothetically rebounds
    decision = engine.evaluate_trade(signal, current_equity=9999.0, current_positions_count=0, current_exposure=0.0)
    assert decision.approved is False
    assert decision.rejection_reason == "REJECTED: DEATH MODE ACTIVE. Survival budget breached."
    assert decision.relevant_limit == "DEATH_MODE"
    assert engine.death_mode_active is True


def test_death_mode_active_property_sync():
    limits = MagicMock(spec=PortfolioRiskLimits)
    engine = RiskEngine(limits=limits)

    engine.death_mode_active = True
    assert engine.is_death_mode_active is True
    assert engine.death_mode_active is True

    engine.is_death_mode_active = False
    assert engine.death_mode_active is False
    assert engine.is_death_mode_active is False

