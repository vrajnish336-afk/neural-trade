import os
import json
import pytest
from datetime import datetime, timezone
from app.backtesting.models import BacktestResult, BacktestTrade
from app.analytics.models import TradeMetrics, EquityMetrics, FullAnalyticsReport
from reports.generate_report import generate_markdown_report
from app.research.robustness.artifact import (
    FoldEvidenceMetrics,
    AggregateEvidenceMetrics,
    WalkForwardEvidenceArtifact,
    load_evidence_from_json
)

def test_evidence_metrics_post_and_pre_cost_labels():
    """Verify that FoldEvidenceMetrics and AggregateEvidenceMetrics provide clear post-cost and pre-cost properties."""
    f = FoldEvidenceMetrics(
        window_id=1,
        boundaries={
            "train_start": "2023-01-01T00:00:00Z", "train_end": "2023-01-10T00:00:00Z",
            "validation_start": "2023-01-10T00:00:00Z", "validation_end": "2023-01-15T00:00:00Z",
            "test_start": "2023-01-15T00:00:00Z", "test_end": "2023-01-20T00:00:00Z"
        },
        trades=5, wins=2, losses=3,
        profit_factor=1.25, expectancy=10.0, max_drawdown_pct=3.0,
        gross_profit=500.0, gross_loss=400.0, net_pnl=100.0,
        entry_costs=20.0, exit_costs=20.0, slippage_costs=40.0, total_costs=80.0
    )

    assert f.post_cost_profit_factor == 1.25
    assert f.post_cost_gross_profit == 500.0
    assert f.post_cost_gross_loss == 400.0
    assert f.pre_cost_net_pnl == 180.0 # 100 net + 80 costs
    assert f.is_cost_adjusted is True

    agg = AggregateEvidenceMetrics(
        total_trades=5, wins=2, losses=3,
        profit_factor=1.25, expectancy=10.0, max_drawdown_pct=3.0,
        gross_profit=500.0, gross_loss=400.0, net_pnl=100.0, total_costs=80.0
    )
    assert agg.post_cost_profit_factor == 1.25
    assert agg.post_cost_gross_profit == 500.0
    assert agg.post_cost_gross_loss == 400.0
    assert agg.pre_cost_net_pnl == 180.0
    assert agg.is_cost_adjusted is True

def test_backtest_result_pre_vs_post_cost_properties():
    """Verify BacktestResult pre-cost and post-cost properties distinguish pre/post cost metrics."""
    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
    t_win = BacktestTrade(
        symbol="BTC_USDT", direction="LONG", entry_time=t0, entry_price=100.0,
        exit_time=t0, exit_price=110.0, quantity=1.0,
        entry_cost=1.0, exit_cost=1.0, slippage_cost=2.0, realized_pnl=6.0, # raw was +10, net is 6
        exit_reason="Take Profit"
    )
    t_loss = BacktestTrade(
        symbol="BTC_USDT", direction="LONG", entry_time=t0, entry_price=100.0,
        exit_time=t0, exit_price=90.0, quantity=1.0,
        entry_cost=1.0, exit_cost=1.0, slippage_cost=2.0, realized_pnl=-14.0, # raw was -10, net is -14
        exit_reason="Stop Loss"
    )

    result = BacktestResult(
        initial_capital=1000.0, final_equity=992.0, total_return_pct=-0.8,
        number_of_trades=2, winning_trades=1, losing_trades=1, win_rate=50.0,
        gross_profit=6.0, gross_loss=14.0, net_profit=-8.0, max_drawdown_pct=1.4,
        average_trade_result=-4.0, profit_factor=6.0 / 14.0, average_holding_period_hours=1.0,
        trades=[t_win, t_loss]
    )

    # Post-cost metrics
    assert result.post_cost_gross_profit == 6.0
    assert result.post_cost_gross_loss == 14.0
    assert abs(result.post_cost_profit_factor - (6.0 / 14.0)) < 1e-6
    assert result.total_costs == 8.0 # (1+1+2) * 2

    # Pre-cost raw metrics
    assert result.pre_cost_gross_profit == 10.0
    assert result.pre_cost_gross_loss == 10.0
    assert result.pre_cost_profit_factor == 1.0

def test_trade_metrics_cost_labeled_properties():
    """Verify TradeMetrics properties clearly label post-cost net PnL and total execution costs."""
    tm = TradeMetrics(
        total_trades=10, winning_trades=4, losing_trades=6, win_rate=40.0,
        gross_pnl=500.0, net_pnl=350.0, total_commission=100.0, total_slippage=50.0,
        average_pnl=35.0, average_win=150.0, average_loss=-50.0, profit_factor=1.5,
        largest_win=200.0, largest_loss=-80.0, max_consecutive_wins=2, max_consecutive_losses=3,
        average_holding_hours=4.5
    )

    assert tm.post_cost_profit_factor == 1.5
    assert tm.post_cost_net_pnl == 350.0
    assert tm.total_execution_costs == 150.0
    assert tm.pre_cost_gross_pnl == 500.0

def test_smoke_artifact_backward_compatibility(tmp_path):
    """Verify existing walk-forward smoke artifact backward compatibility and new label access."""
    art_path = "reports/smoke_walk_forward_artifact.json"
    assert os.path.exists(art_path)

    art = load_evidence_from_json(art_path)
    assert art is not None
    assert art.artifact_id == "4dd5d272-1090-4911-b06f-c84ad3ba8744"
    assert art.reconciled is True

    # Check that aggregate post-cost properties match reported values
    assert abs(art.aggregate.post_cost_profit_factor - 0.6128511253213667) < 1e-6
    assert abs(art.aggregate.post_cost_gross_profit - 1333.2663198006353) < 1e-6
    assert abs(art.aggregate.post_cost_gross_loss - 2175.5141905001765) < 1e-6
    assert abs(art.aggregate.pre_cost_net_pnl - (art.aggregate.net_pnl + art.aggregate.total_costs)) < 1e-6

    # Verify JSON round-trip serialization preservation
    serialized = art.model_dump_json()
    reloaded = WalkForwardEvidenceArtifact.model_validate_json(serialized)
    assert reloaded.artifact_id == art.artifact_id
    assert reloaded.aggregate.gross_profit == art.aggregate.gross_profit
    assert reloaded.aggregate.total_costs == art.aggregate.total_costs

def test_report_generation_labels(tmp_path):
    """Verify generate_markdown_report outputs clear post-cost and cost breakdown labels."""
    report = FullAnalyticsReport(
        backtest_id="test_bt",
        trade_metrics=TradeMetrics(
            total_trades=10, winning_trades=4, losing_trades=6, win_rate=40.0,
            gross_pnl=500.0, net_pnl=350.0, total_commission=100.0, total_slippage=50.0,
            average_pnl=35.0, average_win=150.0, average_loss=-50.0, profit_factor=1.5,
            largest_win=200.0, largest_loss=-80.0, max_consecutive_wins=2, max_consecutive_losses=3,
            average_holding_hours=4.5
        ),
        equity_metrics=EquityMetrics(
            initial_capital=10000.0, final_equity=10350.0, absolute_pnl=350.0,
            total_return_pct=3.5, max_drawdown_pct=2.1, max_drawdown_amount=210.0,
            average_drawdown_pct=1.0, time_in_drawdown_pct=5.0, recovery_periods=1
        ),
        strategy_attribution=[], regime_attribution=[], signal_bucket_attribution=[],
        intelligence_attribution=[], failure_findings=[], strategy_comparisons=[]
    )

    out_file = str(tmp_path / "test_report.md")
    generate_markdown_report(report, output_path=out_file)

    content = open(out_file, encoding="utf-8").read()
    assert "Post-Cost Profit Factor" in content
    assert "Net PnL (After Costs)" in content
    assert "Included Execution Costs" in content
    assert "Pre-Cost Gross PnL" in content

def test_walk_forward_artifact_report_formatting_schema():
    """Regression test ensuring report generation using AggregateEvidenceMetrics uses the verified schema API."""
    agg = AggregateEvidenceMetrics(
        total_trades=8, wins=2, losses=6, profit_factor=0.82,
        expectancy=-37.51, max_drawdown_pct=7.39, gross_profit=1364.55,
        gross_loss=1664.61, net_pnl=-300.06, total_costs=311.62
    )
    # Verify valid attributes exist and match expected values
    assert hasattr(agg, "total_costs")
    assert not hasattr(agg, "total_entry_costs")
    assert not hasattr(agg, "total_exit_costs")
    assert not hasattr(agg, "total_slippage_costs")

    # Verify report formatting using the verified API succeeds without AttributeError
    report_line = f"Total Costs: ${agg.total_costs:.2f}"
    assert report_line == "Total Costs: $311.62"

    # Verify fold-level cost breakdown retrieval uses FoldEvidenceMetrics
    f1 = FoldEvidenceMetrics(
        window_id=1,
        boundaries={
            "train_start": "2024-01-01T00:00:00Z", "train_end": "2024-01-10T00:00:00Z",
            "validation_start": "2024-01-10T00:00:00Z", "validation_end": "2024-01-15T00:00:00Z",
            "test_start": "2024-01-15T00:00:00Z", "test_end": "2024-01-20T00:00:00Z"
        },
        trades=8, wins=2, losses=6, profit_factor=0.82, expectancy=-37.51,
        max_drawdown_pct=7.39, gross_profit=1364.55, gross_loss=1664.61, net_pnl=-300.06,
        entry_costs=78.50, exit_costs=77.00, slippage_costs=156.12, total_costs=311.62
    )
    entry_costs = sum(f.entry_costs for f in [f1])
    exit_costs = sum(f.exit_costs for f in [f1])
    slippage_costs = sum(f.slippage_costs for f in [f1])
    assert entry_costs == 78.50
    assert exit_costs == 77.00
    assert slippage_costs == 156.12
    assert round(entry_costs + exit_costs + slippage_costs, 2) == round(agg.total_costs, 2)

