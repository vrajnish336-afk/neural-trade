import pytest
from app.risk.position_sizing import (
    calculate_fixed_percentage_risk,
    calculate_position_size_by_stop_distance,
    calculate_atr_stop
)
from app.risk.limits import PortfolioRiskLimits
from app.backtesting.models import BacktestTrade
from datetime import datetime, timezone

def test_fixed_percentage_risk():
    assert calculate_fixed_percentage_risk(10000.0, 0.01) == 100.0
    assert calculate_fixed_percentage_risk(-500.0, 0.01) == 0.0

def test_position_sizing_by_stop():
    # Risk 100, entry 50, stop 40 -> distance 10 -> qty 10
    qty = calculate_position_size_by_stop_distance(100.0, 50.0, 40.0)
    assert qty == 10.0
    
    # Zero distance
    assert calculate_position_size_by_stop_distance(100.0, 50.0, 50.0) == 0.0
    
    # Invalid prices
    assert calculate_position_size_by_stop_distance(100.0, -10.0, 40.0) == 0.0

def test_atr_stop():
    assert calculate_atr_stop("LONG", 100.0, 2.0, 1.5) == 97.0
    assert calculate_atr_stop("SHORT", 100.0, 2.0, 1.5) == 103.0
    
def test_portfolio_limits():
    limits = PortfolioRiskLimits(initial_equity=10000.0, max_positions=2, daily_loss_limit_pct=0.05)
    
    # Can open initial
    assert limits.can_open_new_position(0, 0.0, 10000.0)[0] is True
    
    # Exceed position count
    assert limits.can_open_new_position(2, 5000.0, 10000.0)[0] is False
    
    # Exceed exposure
    assert limits.can_open_new_position(1, 15000.0, 10000.0)[0] is False
    
    # Update with losing trade
    trade = BacktestTrade(
        symbol="BTC", direction="LONG", entry_time=datetime.now(timezone.utc), exit_time=datetime.now(timezone.utc),
        entry_price=100, exit_price=90, quantity=60, realized_pnl=-600, exit_reason="SL", entry_cost=0, exit_cost=0, slippage_cost=0
    )
    limits.update_from_closed_trade(trade)
    
    assert limits.loss_streak == 1
    assert limits.can_open_new_position(0, 0.0, 10000.0)[0] is False # Blocked due to daily loss
    
    limits.reset_daily_loss()
    assert limits.can_open_new_position(0, 0.0, 10000.0)[0] is True
