"""
Phase 58 — DrawdownService focused tests
==========================================
Covers:
  - Increasing equity (no drawdown)
  - Peak followed by decline
  - Recovery to prior peak
  - Multiple drawdown periods
  - Current vs maximum drawdown distinction
  - Zero / invalid peak
  - Empty / insufficient history
  - Negative / malformed values
  - Out-of-order timestamps
  - Duplicate snapshots
  - Partial history flag
  - No fabricated snapshots
"""

import pytest
from app.risk.drawdown import DrawdownService, DrawdownResult, DrawdownStatus


def _row(timestamp: str, equity: float) -> dict:
    """Helper: simulate a sqlite3.Row-compatible dict."""
    return {"timestamp": timestamp, "current_equity": equity}


# -------------------------------------------------------------------------
# Empty / insufficient history
# -------------------------------------------------------------------------

def test_empty_snapshots_returns_insufficient():
    svc = DrawdownService()
    result = svc.calculate([])
    assert result.status == DrawdownStatus.INSUFFICIENT_DATA
    assert result.current_drawdown_pct == 0.0


def test_single_snapshot_returns_insufficient():
    svc = DrawdownService()
    result = svc.calculate([_row("2023-01-01T00:00:00", 10000.0)])
    assert result.status == DrawdownStatus.INSUFFICIENT_DATA


# -------------------------------------------------------------------------
# Invalid / malformed data
# -------------------------------------------------------------------------

def test_zero_initial_equity_returns_invalid():
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 0.0),
        _row("2023-01-02T00:00:00", 10000.0),
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.INVALID_DATA


def test_negative_initial_equity_returns_invalid():
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", -500.0),
        _row("2023-01-02T00:00:00", 10000.0),
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.INVALID_DATA


def test_malformed_row_skipped_leaves_insufficient():
    """A row missing the 'current_equity' key is skipped; with only 1 valid left → INSUFFICIENT."""
    svc = DrawdownService()
    rows = [
        {"timestamp": "2023-01-01T00:00:00"},          # missing equity
        _row("2023-01-02T00:00:00", 10000.0),
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.INSUFFICIENT_DATA


def test_all_rows_malformed_returns_insufficient():
    svc = DrawdownService()
    rows = [{"bad": "data"}, {"also_bad": 42}]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.INSUFFICIENT_DATA


# -------------------------------------------------------------------------
# Mathematics — correct drawdown calculation
# -------------------------------------------------------------------------

def test_monotonically_increasing_equity_zero_drawdown():
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 10100.0),
        _row("2023-01-03T00:00:00", 10200.0),
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    assert result.current_drawdown_pct == 0.0
    assert result.max_drawdown_pct == 0.0
    assert result.running_peak_equity == 10200.0


def test_peak_then_decline():
    """10000 → 11000 → 9900: peak=11000, current_dd = (11000-9900)/11000*100 ≈ 10%"""
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 11000.0),
        _row("2023-01-03T00:00:00", 9900.0),
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    expected_dd = (11000.0 - 9900.0) / 11000.0 * 100
    assert abs(result.current_drawdown_pct - expected_dd) < 0.01
    assert result.max_drawdown_pct == result.current_drawdown_pct   # only 1 drawdown period
    assert result.running_peak_equity == 11000.0


def test_recovery_to_prior_peak_resets_current_drawdown():
    """
    10000 → 11000 → 9000 → 11000
    After recovery: current_dd = 0, but max_dd captured the 9000 trough.
    """
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 11000.0),
        _row("2023-01-03T00:00:00", 9000.0),
        _row("2023-01-04T00:00:00", 11000.0),   # full recovery
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    assert result.current_drawdown_pct == 0.0
    expected_max = (11000.0 - 9000.0) / 11000.0 * 100
    assert abs(result.max_drawdown_pct - expected_max) < 0.01


def test_multiple_drawdown_periods_max_captures_worst():
    """
    Peak 12000, small trough 11500, then bigger trough 9000.
    max_dd must track the 9000 trough, not the 11500 one.
    """
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 12000.0),  # peak
        _row("2023-01-03T00:00:00", 11500.0),  # minor dip
        _row("2023-01-04T00:00:00", 12000.0),  # recover
        _row("2023-01-05T00:00:00", 9000.0),   # bigger dip
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    expected_max = (12000.0 - 9000.0) / 12000.0 * 100
    assert abs(result.max_drawdown_pct - expected_max) < 0.01
    assert result.current_drawdown_pct == result.max_drawdown_pct   # last point is worst


def test_current_vs_max_drawdown_distinct():
    """
    Worst trough is mid-series; last point is partially recovered.
    current_dd < max_dd.
    """
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 12000.0),   # peak
        _row("2023-01-03T00:00:00", 8000.0),    # worst trough
        _row("2023-01-04T00:00:00", 10000.0),   # partial recovery
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    expected_max = (12000.0 - 8000.0) / 12000.0 * 100
    expected_current = (12000.0 - 10000.0) / 12000.0 * 100
    assert abs(result.max_drawdown_pct - expected_max) < 0.01
    assert abs(result.current_drawdown_pct - expected_current) < 0.01
    assert result.current_drawdown_pct < result.max_drawdown_pct


# -------------------------------------------------------------------------
# Chronology and persistence
# -------------------------------------------------------------------------

def test_out_of_order_timestamps_are_sorted():
    """Service must sort rows by timestamp, not rely on storage order."""
    svc = DrawdownService()
    rows = [
        _row("2023-01-03T00:00:00", 9000.0),   # chronologically last (worst)
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 12000.0),  # peak
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    # After sorting: 10000 → 12000 → 9000. Peak = 12000, current_dd > 0
    assert result.running_peak_equity == 12000.0
    assert result.current_drawdown_pct > 0.0


def test_duplicate_timestamps_are_handled_safely():
    """Duplicate snapshots (same timestamp, same equity) must not blow up."""
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-01T00:00:00", 10000.0),  # duplicate
        _row("2023-01-02T00:00:00", 9500.0),
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    assert result.running_peak_equity == 10000.0


def test_partial_history_flag_propagated():
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 9800.0),
    ]
    result = svc.calculate(rows, has_partial_history=True)
    assert result.status == DrawdownStatus.OK
    assert result.has_partial_history is True


def test_no_partial_history_flag_by_default():
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 10000.0),
    ]
    result = svc.calculate(rows)
    assert result.has_partial_history is False


def test_observation_window_timestamps_match_first_last():
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-05T00:00:00", 10500.0),
    ]
    result = svc.calculate(rows)
    assert result.observation_start == "2023-01-01T00:00:00"
    assert result.observation_end == "2023-01-05T00:00:00"
    assert result.snapshot_count == 2


def test_no_fabricated_snapshots_insufficient_returns_empty_metrics():
    """Ensure that no default or synthetic equity is injected on insufficient data."""
    svc = DrawdownService()
    result = svc.calculate([])
    assert result.running_peak_equity == 0.0
    assert result.current_equity == 0.0
    assert result.observation_start is None
    assert result.observation_end is None


# -------------------------------------------------------------------------
# Non-positive mid-series equity (anomaly tolerance)
# -------------------------------------------------------------------------

def test_non_positive_mid_series_equity_skipped_in_peak_tracking():
    """A zero or negative equity mid-series is skipped without crashing."""
    svc = DrawdownService()
    rows = [
        _row("2023-01-01T00:00:00", 10000.0),
        _row("2023-01-02T00:00:00", 0.0),       # anomalous — skipped
        _row("2023-01-03T00:00:00", 9800.0),
    ]
    result = svc.calculate(rows)
    assert result.status == DrawdownStatus.OK
    assert result.running_peak_equity == 10000.0
    assert result.current_equity == 9800.0
