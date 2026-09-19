"""
Phase 58 — RiskEngine drawdown veto tests
==========================================
Covers:
  - Below threshold → approved
  - At threshold → veto
  - Above threshold → veto
  - INSUFFICIENT_DATA → monitoring only (not a hard block)
  - INVALID_DATA → veto
  - None input → veto
  - Existing evaluate_trade() not broken
  - No position sizing changes from check_drawdown
  - No AI override or live execution
"""

import pytest
from unittest.mock import MagicMock
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.drawdown import DrawdownResult, DrawdownStatus


def _make_engine(halt_pct: float = 20.0) -> RiskEngine:
    limits = PortfolioRiskLimits(initial_equity=10000.0, max_drawdown_halt_pct=halt_pct)
    return RiskEngine(limits)


def _ok_result(current_dd: float, max_dd: float = None) -> DrawdownResult:
    return DrawdownResult(
        status=DrawdownStatus.OK,
        current_drawdown_pct=current_dd,
        max_drawdown_pct=max_dd or current_dd,
        running_peak_equity=12000.0,
        current_equity=12000.0 * (1 - current_dd / 100),
        observation_start="2023-01-01T00:00:00",
        observation_end="2023-01-10T00:00:00",
        snapshot_count=5,
    )


def _insufficient_result() -> DrawdownResult:
    return DrawdownResult(
        status=DrawdownStatus.INSUFFICIENT_DATA,
        reason="Need at least 2 snapshots, got 1.",
    )


def _invalid_result() -> DrawdownResult:
    return DrawdownResult(
        status=DrawdownStatus.INVALID_DATA,
        reason="Initial equity snapshot is non-positive (0.0).",
    )


# -------------------------------------------------------------------------
# Threshold comparisons
# -------------------------------------------------------------------------

def test_below_threshold_approved():
    engine = _make_engine(halt_pct=20.0)
    approved, reason = engine.check_drawdown(_ok_result(current_dd=10.0))
    assert approved is True
    assert "OK" in reason or "within" in reason.lower() or "10.00" in reason


def test_at_threshold_veto():
    """At exactly the threshold drawdown should be vetoed (>= comparison)."""
    engine = _make_engine(halt_pct=20.0)
    approved, reason = engine.check_drawdown(_ok_result(current_dd=20.0))
    assert approved is False
    assert "VETO" in reason or "blocked" in reason.lower()


def test_above_threshold_veto():
    engine = _make_engine(halt_pct=20.0)
    approved, reason = engine.check_drawdown(_ok_result(current_dd=25.0))
    assert approved is False
    assert "VETO" in reason or "blocked" in reason.lower()


def test_zero_drawdown_always_approved():
    engine = _make_engine(halt_pct=20.0)
    approved, _ = engine.check_drawdown(_ok_result(current_dd=0.0))
    assert approved is True


# -------------------------------------------------------------------------
# Edge-case inputs
# -------------------------------------------------------------------------

def test_none_input_veto():
    """None DrawdownResult must never be treated as safe."""
    engine = _make_engine()
    approved, reason = engine.check_drawdown(None)
    assert approved is False
    assert "REVIEW_REQUIRED" in reason or "None" in reason


def test_insufficient_data_monitoring_only():
    """< 2 snapshots: not a hard block (bootstrap grace), but surfaces warning."""
    engine = _make_engine()
    approved, reason = engine.check_drawdown(_insufficient_result())
    assert approved is True
    assert "INSUFFICIENT" in reason or "monitoring" in reason.lower()


def test_invalid_data_veto():
    engine = _make_engine()
    approved, reason = engine.check_drawdown(_invalid_result())
    assert approved is False
    assert "VETO" in reason or "REVIEW_REQUIRED" in reason


# -------------------------------------------------------------------------
# Limit attribute
# -------------------------------------------------------------------------

def test_limits_stores_halt_pct():
    limits = PortfolioRiskLimits(initial_equity=10000.0, max_drawdown_halt_pct=15.0)
    assert limits.max_drawdown_halt_pct == 15.0


def test_default_halt_pct_is_20():
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    assert limits.max_drawdown_halt_pct == 20.0


# -------------------------------------------------------------------------
# evaluate_trade unchanged — no sizing changes from drawdown
# -------------------------------------------------------------------------

def test_evaluate_trade_unaffected_by_drawdown():
    """
    check_drawdown is a separate call.  evaluate_trade must not be altered
    by anything done to drawdown — they are independent code paths.
    """
    from app.core.models import TradingSignal
    from datetime import datetime, timezone
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    engine = RiskEngine(limits)

    signal = TradingSignal(
        symbol="BTC/USD",
        direction="LONG",
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        timestamp=datetime.now(timezone.utc),
        strategy="test",
        confidence=0.8,
        reason="phase58 test",
    )

    # Evaluate trade with OK drawdown state (not passed to evaluate_trade)
    decision = engine.evaluate_trade(
        signal=signal,
        current_equity=10000.0,
        current_positions_count=0,
        current_exposure=0.0,
    )
    # Position sizing must be non-zero for a valid signal
    assert decision.approved is True
    assert decision.position_size > 0


def test_check_drawdown_does_not_modify_position_size():
    """check_drawdown is read-only; calling it must not change the engine state."""
    engine = _make_engine()
    before_risk_per_trade = engine.risk_per_trade_pct

    engine.check_drawdown(_ok_result(current_dd=5.0))
    engine.check_drawdown(_ok_result(current_dd=25.0))
    engine.check_drawdown(None)

    assert engine.risk_per_trade_pct == before_risk_per_trade


# -------------------------------------------------------------------------
# Safety: no live trading linkage
# -------------------------------------------------------------------------

def test_no_live_execution_attribute_on_engine():
    """RiskEngine must not expose any live-broker or live-execution attributes."""
    engine = _make_engine()
    assert not hasattr(engine, "live_broker")
    assert not hasattr(engine, "execute_live")
    assert not hasattr(engine, "live_order")
