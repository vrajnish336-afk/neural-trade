import pytest
from datetime import datetime, timezone
from app.backtesting.models import BacktestTrade
from app.analytics.performance import calculate_trade_metrics, calculate_equity_metrics
from app.analytics.attribution import _calculate_attribution
from app.analytics.walk_forward import split_walk_forward_windows
from app.core.models import MarketBar

def _make_trade(pnl, direction="LONG", strategy="Trend", regime="TRENDING_UP", intel="POSITIVE"):
    return BacktestTrade(
        symbol="BTC", direction=direction,
        entry_time=datetime.now(timezone.utc),
        entry_price=100.0, exit_time=datetime.now(timezone.utc),
        exit_price=100.0 + pnl if direction == "LONG" else 100.0 - pnl,
        quantity=1.0, entry_cost=0.0, exit_cost=0.0, slippage_cost=0.0, realized_pnl=pnl,
        exit_reason="Test", regime=regime, score=50.0, strategies=strategy,
        sentiment_label=intel, anomaly_flags="", fakeout_risk="LOW"
    )

def test_calculate_trade_metrics():
    trades = [
        _make_trade(100),
        _make_trade(-50),
        _make_trade(200),
        _make_trade(-50)
    ]
    metrics = calculate_trade_metrics(trades)
    
    assert metrics.total_trades == 4
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 2
    assert metrics.win_rate == 50.0
    assert metrics.net_pnl == 200
    assert metrics.profit_factor == 3.0 # (100 + 200) / (50 + 50) = 300 / 100

def test_calculate_trade_metrics_empty():
    metrics = calculate_trade_metrics([])
    assert metrics.total_trades == 0
    assert metrics.win_rate == 0.0

def test_calculate_equity_metrics():
    eq_curve = [
        {'equity': 1000},
        {'equity': 1100},
        {'equity': 1050},
        {'equity': 1200}
    ]
    metrics = calculate_equity_metrics(eq_curve, 1000)
    
    assert metrics.initial_capital == 1000
    assert metrics.final_equity == 1200
    assert metrics.absolute_pnl == 200
    assert metrics.total_return_pct == 20.0
    
    # max drawdown is from 1100 to 1050 -> 50 / 1100 = 0.04545... -> ~4.54%
    assert 4.5 < metrics.max_drawdown_pct < 4.6

def test_walk_forward_splits():
    bars = [MarketBar(symbol="A", timestamp=datetime(2023,1,1,tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1) for _ in range(100)]
    
    windows = split_walk_forward_windows(bars, num_windows=2, train_ratio=0.7)
    assert len(windows) == 2
    
    w1_name, w1_train, w1_test = windows[0]
    assert w1_name == "Window 1"
    assert len(w1_train) == 35 # 70% of 50
    assert len(w1_test) == 15
    
    w2_name, w2_train, w2_test = windows[1]
    assert len(w2_train) == 35
    assert len(w2_test) == 15
    
    # Assert non-overlapping and chronological
    assert w1_train[0] is bars[0]
    assert w2_train[0] is bars[50]
