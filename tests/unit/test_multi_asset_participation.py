import pytest
from app.diagnostics.participation import calculate_participation_metrics, format_counterfactual_disclaimer

def test_calculate_participation_metrics_active():
    res = calculate_participation_metrics(
        executed_entries=10, down_vetoes=5, unknown_vetoes=0, dup_blocked=5,
        closed_trades=8, open_positions=2, realized_pnl=150.0, unrealized_pnl=20.0, max_dd_pct=1.5
    )
    assert res["eligible_signals"] == 20
    assert res["executed_entries"] == 10
    assert res["participation_rate_pct"] == 50.0
    assert res["zero_exposure"] is False
    assert res["status_flag"] == "ACTIVE_PARTICIPATION"
    assert res["warning"] is None

def test_calculate_participation_metrics_zero_exposure():
    res = calculate_participation_metrics(
        executed_entries=0, down_vetoes=50, unknown_vetoes=0, dup_blocked=25,
        closed_trades=0, open_positions=0, realized_pnl=0.0, unrealized_pnl=0.0, max_dd_pct=0.0
    )
    assert res["eligible_signals"] == 75
    assert res["executed_entries"] == 0
    assert res["participation_rate_pct"] == 0.0
    assert res["zero_exposure"] is True
    assert res["status_flag"] == "ZERO_EXPOSURE_SUPPRESSION"
    assert "reflect total market exposure suppression" in res["warning"]

def test_calculate_participation_metrics_zero_denominator():
    res = calculate_participation_metrics(
        executed_entries=0, down_vetoes=0, unknown_vetoes=0, dup_blocked=0,
        closed_trades=0, open_positions=0, realized_pnl=0.0, unrealized_pnl=0.0, max_dd_pct=0.0
    )
    assert res["eligible_signals"] == 0
    assert res["participation_rate_pct"] == 0.0
    assert res["zero_exposure"] is True

def test_counterfactual_disclaimer():
    disclaimer = format_counterfactual_disclaimer()
    assert "HYPOTHETICAL COUNTERFACTUAL NOTE" in disclaimer
    assert "Concurrency limits" in disclaimer
    assert "transaction fee" in disclaimer
