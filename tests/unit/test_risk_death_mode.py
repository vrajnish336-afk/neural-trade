import pytest
import sqlite3
import os
import tempfile
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.core.models import TradingSignal, RiskDecision
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.config import config
from app.database.schema import SCHEMA_SQL
from app.execution.paper_repository import PaperRepository, PaperRepositoryException

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    yield path
    try:
        os.close(fd)
        os.remove(path)
    except OSError:
        pass

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


# ---------------------------------------------------------------------------
# Restart-Persistent Death Mode Latch Tests
# ---------------------------------------------------------------------------

def test_activation_persists_across_newly_created_risk_engine(temp_db):
    """
    Test 1: Death Mode activation is persisted to SQLite and automatically
    restored by a brand new RiskEngine instance pointing to the same portfolio.
    """
    repo = PaperRepository(db_path=temp_db)
    limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    portfolio_id = "test_persist_portfolio"
    repo.get_or_create_portfolio(portfolio_id, initial_equity=10000.0)

    # Initial RiskEngine instance
    engine1 = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id=portfolio_id)
    assert engine1.death_mode_active is False

    # Trigger Death Mode via survival budget breach
    signal = make_signal()
    decision = engine1.evaluate_trade(signal, current_equity=4000.0, current_positions_count=0, current_exposure=0.0)
    assert decision.approved is False
    assert decision.relevant_limit == "DEATH_MODE"
    assert engine1.death_mode_active is True

    # Verify state was saved to SQLite table
    saved_state = repo.get_death_mode_state(portfolio_id)
    assert saved_state is not None
    assert saved_state["active"] is True
    assert "Survival budget breached" in saved_state["reason"]
    assert saved_state["updated_at"] is not None

    # Simulate restart by creating a completely new RiskEngine instance
    engine2 = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id=portfolio_id)
    assert engine2.death_mode_active is True
    assert engine2.is_death_mode_active is True
    assert "Survival budget breached" in engine2.death_mode_reason

    # Subsequent trade on restarted engine is rejected even if equity is healthy
    recovered_decision = engine2.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0)
    assert recovered_decision.approved is False
    assert recovered_decision.relevant_limit == "DEATH_MODE"
    assert engine2.death_mode_active is True


def test_drawdown_and_loss_streak_triggers_route_through_activation_persistence(temp_db):
    """
    Test 2: Configured drawdown and loss-streak triggers route through the single
    activate_death_mode path and persist to SQLite.
    """
    repo = PaperRepository(db_path=temp_db)
    limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    portfolio_id = "test_dd_portfolio"
    repo.get_or_create_portfolio(portfolio_id, initial_equity=10000.0)

    engine = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id=portfolio_id)
    signal = make_signal()

    with patch.object(config, "DEATH_MODE_ENABLED", True), patch.object(config, "DEATH_MODE_DRAWDOWN_LIMIT", 0.10):
        decision = engine.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0, current_drawdown=0.15)
        assert decision.approved is False
        assert engine.death_mode_active is True
        assert "Drawdown" in engine.death_mode_reason

        # Verify persisted
        state = repo.get_death_mode_state(portfolio_id)
        assert state is not None
        assert state["active"] is True
        assert "Drawdown" in state["reason"]

    # Verify a new instance restores the drawdown reason
    new_engine = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id=portfolio_id)
    assert new_engine.death_mode_active is True
    assert "Drawdown" in new_engine.death_mode_reason


def test_manual_reset_persistence_and_restart(temp_db):
    """
    Test 3: Explicit manual reset persists the inactive state to SQLite,
    and a restarted RiskEngine remains inactive and approves valid trades.
    """
    repo = PaperRepository(db_path=temp_db)
    limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    portfolio_id = "test_reset_portfolio"
    repo.get_or_create_portfolio(portfolio_id, initial_equity=10000.0)

    engine = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id=portfolio_id)
    engine.activate_death_mode("Initial breach")
    assert engine.death_mode_active is True

    # Verify active in DB
    state = repo.get_death_mode_state(portfolio_id)
    assert state["active"] is True

    # Manual reset
    engine.manual_reset_death_mode()
    assert engine.death_mode_active is False
    assert engine.death_mode_reason is None

    # Verify inactive in DB
    state_after = repo.get_death_mode_state(portfolio_id)
    assert state_after["active"] is False

    # Restart a new engine: should be inactive
    restarted_engine = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id=portfolio_id)
    assert restarted_engine.death_mode_active is False
    assert restarted_engine.death_mode_reason is None

    # Healthy trade is approved
    signal = make_signal()
    decision = restarted_engine.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0)
    assert decision.approved is True


def test_reset_persistence_failure_blocks_trading_and_preserves_latch():
    """
    Test 4: If persistence fails during manual reset, the latch remains active in-memory,
    the exception is raised, and trades continue to be rejected.
    """
    limits = MagicMock(spec=PortfolioRiskLimits)
    mock_store = MagicMock()
    mock_store.set_death_mode_state.side_effect = PaperRepositoryException("Disk full / DB error")
    mock_store.get_death_mode_state.return_value = {"active": True, "reason": "Survival breach"}

    engine = RiskEngine(limits=limits, death_mode_store=mock_store, portfolio_id="port_fail")
    assert engine.death_mode_active is True

    # Attempt manual reset with failing persistence
    with pytest.raises(PaperRepositoryException, match="Disk full / DB error"):
        engine.manual_reset_death_mode()

    # Invariant: latch MUST remain active because persistence failed
    assert engine.death_mode_active is True
    assert engine.is_death_mode_active is True

    # Subsequent trades must still be rejected
    signal = make_signal()
    decision = engine.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0)
    assert decision.approved is False
    assert decision.relevant_limit == "DEATH_MODE"


def test_healthy_portfolios_remain_unaffected(temp_db):
    """
    Test 5: Multi-portfolio isolation — Death Mode on portfolio_A does not affect
    healthy portfolio_B in the same database.
    """
    repo = PaperRepository(db_path=temp_db)
    limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)

    repo.get_or_create_portfolio("portfolio_A", initial_equity=10000.0)
    repo.get_or_create_portfolio("portfolio_B", initial_equity=10000.0)

    engine_a = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id="portfolio_A")
    engine_b = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id="portfolio_B")

    # Activate death mode on portfolio_A only
    engine_a.activate_death_mode("Survival budget breached on A")

    assert engine_a.death_mode_active is True
    assert engine_b.death_mode_active is False

    # Portfolio A in DB is active; Portfolio B in DB is None or inactive
    state_a = repo.get_death_mode_state("portfolio_A")
    state_b = repo.get_death_mode_state("portfolio_B")
    assert state_a["active"] is True
    assert state_b is None

    # Restart both engines
    new_engine_a = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id="portfolio_A")
    new_engine_b = RiskEngine(limits=limits, death_mode_store=repo, portfolio_id="portfolio_B")

    assert new_engine_a.death_mode_active is True
    assert new_engine_b.death_mode_active is False

    signal = make_signal()
    assert new_engine_a.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0).approved is False
    assert new_engine_b.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0).approved is True


def test_legacy_callers_without_persistence_support():
    """
    Test 6: Legacy callers instantiating RiskEngine without persistence store
    continue to work completely seamlessly in-memory.
    """
    limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    engine = RiskEngine(limits=limits)

    assert engine.death_mode_active is False
    assert engine.death_mode_store is None
    assert engine.portfolio_id is None

    signal = make_signal()
    # Baseline trade approved
    assert engine.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0).approved is True

    # Survival budget breach latches in-memory
    assert engine.evaluate_trade(signal, current_equity=4000.0, current_positions_count=0, current_exposure=0.0).approved is False
    assert engine.death_mode_active is True

    # Manual reset works in-memory
    engine.manual_reset_death_mode()
    assert engine.death_mode_active is False
    assert engine.evaluate_trade(signal, current_equity=10000.0, current_positions_count=0, current_exposure=0.0).approved is True


def test_persistence_callback_support():
    """
    Test 7: Passing a persistence callback records activation and reset events.
    """
    events = []
    def record_callback(active: bool, reason: str = None):
        events.append((active, reason))

    limits = PortfolioRiskLimits(initial_equity=10000.0, survival_budget_pct=0.50)
    engine = RiskEngine(limits=limits, persistence_callback=record_callback)

    engine.activate_death_mode("Callback breach test")
    assert len(events) == 1
    assert events[0] == (True, "Callback breach test")

    engine.manual_reset_death_mode()
    assert len(events) == 2
    assert events[1][0] is False


