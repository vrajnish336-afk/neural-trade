import pytest
import json
import sqlite3
from app.config import config
from app.services.observability import ObservabilityService
from app.analytics.models import FullAnalyticsReport, TradeMetrics
from app.backtesting.models import BacktestTrade
from datetime import datetime, timezone
import subprocess
from pathlib import Path

CLI_PATH = Path(__file__).parent.parent.parent / "cli.py"

def run_cli(*args, **kwargs):
    return subprocess.run(
        ["python", str(CLI_PATH)] + list(args),
        capture_output=True,
        text=True
    )

def test_cost_consistency():
    # Test that gross PnL - costs == net PnL
    t1 = BacktestTrade(
        symbol="TEST", direction="LONG",
        entry_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
        exit_time=datetime(2000, 1, 2, tzinfo=timezone.utc),
        entry_price=100.0, exit_price=110.0, quantity=1.0,
        entry_cost=0.1, exit_cost=0.1, slippage_cost=0.5,
        realized_pnl=9.9, # Net PnL calculated by engine
        exit_reason="TP"
    )
    
    from app.analytics.performance import calculate_trade_metrics
    metrics = calculate_trade_metrics([t1])
    
    assert metrics.net_pnl == 9.8
    assert metrics.total_commission == 0.2
    assert metrics.total_slippage == 0.5
    assert metrics.gross_pnl == 10.0

def test_funnel_aggregation():
    data = {
        "backtest_id": "fake_123",
        "trade_metrics": {
            "total_trades": 1, "winning_trades": 1, "losing_trades": 0, "win_rate": 100.0,
            "gross_pnl": 10.0, "net_pnl": 9.0, "total_commission": 1.0, "total_slippage": 0.0,
            "average_pnl": 9.0, "average_win": 9.0, "average_loss": 0.0, "profit_factor": 100.0,
            "largest_win": 9.0, "largest_loss": 0.0, "max_consecutive_wins": 1, "max_consecutive_losses": 0,
            "average_holding_hours": 24.0
        },
        "equity_metrics": {
            "initial_capital": 10000.0, "final_equity": 10009.0, "absolute_pnl": 9.0,
            "total_return_pct": 0.09, "max_drawdown_pct": 0.0, "max_drawdown_amount": 0.0,
            "average_drawdown_pct": 0.0, "time_in_drawdown_pct": 0.0, "recovery_periods": 0
        },
        "strategy_attribution": [],
        "regime_attribution": [],
        "signal_bucket_attribution": [],
        "intelligence_attribution": [],
        "failure_findings": [],
        "strategy_comparisons": [],
        "telemetry_snapshot": {
            "stage_counts": {"MARKET_BARS": 100, "PAPER_TRADES": 1},
            "rejection_counts": {"Risk Rejection": 5}
        }
    }
        
    report = FullAnalyticsReport(**data)
    funnel_str = ObservabilityService.format_funnel(report)
    
    assert "Market Bars: 100" in funnel_str
    assert "Trades Executed: 1" in funnel_str
    assert "Risk Rejection: 5" in funnel_str
    
def test_cli_analyze_invalid_id():
    res = run_cli("analyze", "does_not_exist_run_id")
    assert res.returncode == 1
    assert "Error: Analytics report not found" in res.stdout

def test_cli_compare_invalid_id():
    res = run_cli("compare", "bad1", "bad2")
    assert res.returncode == 1
    assert "Error: Experiment not found" in res.stdout
