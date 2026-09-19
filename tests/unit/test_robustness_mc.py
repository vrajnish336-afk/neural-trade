import pytest
from datetime import datetime, timezone
import numpy as np
from app.backtesting.models import BacktestTrade
from app.research.robustness.monte_carlo import run_monte_carlo_robustness

def test_monte_carlo_reproducibility():
    t1 = datetime(2022, 1, 1, tzinfo=timezone.utc)
    trades = [
        BacktestTrade(symbol="A", direction="LONG", entry_time=t1, entry_price=100, exit_time=t1, exit_price=110, quantity=1, entry_cost=0, exit_cost=0, slippage_cost=0, realized_pnl=10.0, exit_reason=""),
        BacktestTrade(symbol="A", direction="LONG", entry_time=t1, entry_price=110, exit_time=t1, exit_price=105, quantity=1, entry_cost=0, exit_cost=0, slippage_cost=0, realized_pnl=-5.0, exit_reason=""),
        BacktestTrade(symbol="A", direction="LONG", entry_time=t1, entry_price=105, exit_time=t1, exit_price=120, quantity=1, entry_cost=0, exit_cost=0, slippage_cost=0, realized_pnl=15.0, exit_reason=""),
    ]
    
    res1 = run_monte_carlo_robustness(trades, initial_capital=1000.0, simulations=100, seed=42)
    res2 = run_monte_carlo_robustness(trades, initial_capital=1000.0, simulations=100, seed=42)
    
    assert res1.median_return_pct == res2.median_return_pct
    assert res1.p05_return_pct == res2.p05_return_pct
    assert res1.p95_return_pct == res2.p95_return_pct

def test_monte_carlo_percentile():
    t1 = datetime(2022, 1, 1, tzinfo=timezone.utc)
    trades = [
        BacktestTrade(symbol="A", direction="LONG", entry_time=t1, entry_price=100, exit_time=t1, exit_price=110, quantity=1, entry_cost=0, exit_cost=0, slippage_cost=0, realized_pnl=10.0, exit_reason="")
    ] * 50
    
    res = run_monte_carlo_robustness(trades, initial_capital=1000.0, simulations=100, seed=42)
    # Since all trades are +10, every permutation results in exactly +500 PnL
    assert res.p05_return_pct == 50.0
    assert res.p95_return_pct == 50.0
