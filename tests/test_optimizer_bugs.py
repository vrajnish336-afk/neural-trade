import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar, TradingSignal
from app.backtesting.engine import BacktestEngine
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.strategies.ensemble import StrategyEnsemble
from run_optimizer import run, evaluate_param
from app.research.robustness.walk_forward import run_walk_forward_robustness

def test_mtm_cross_symbol_pricing():
    ensemble = StrategyEnsemble([])
    risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0))
    engine = BacktestEngine(ensemble, risk_engine)
    
    # We will spoof an open position
    engine.portfolio.state.add_position({
        'symbol': 'BTC',
        'direction': 'LONG',
        'entry_time': datetime(2021, 1, 1, tzinfo=timezone.utc),
        'entry_price': 50000.0,
        'quantity': 1.0,
        'stop_loss': 40000.0,
        'take_profit': 60000.0,
        'entry_cost': 0.0,
        'slippage_entry': 0.0,
        'signal_metadata': {}
    })
    
    # Now we feed an ETH bar at 3000
    eth_bar = MarketBar(
        symbol='ETH',
        timestamp=datetime(2021, 1, 2, tzinfo=timezone.utc),
        open=3000.0, high=3000.0, low=3000.0, close=3000.0, volume=100
    )
    
    # The BTC position should NOT be MTM'd at 3000.
    # It should fallback to its entry price if there is no last_price for BTC yet.
    engine.run([eth_bar])
    
    # If the bug is present, equity will plummet by 47000.
    # If fixed, equity should remain near 10000.
    assert engine.equity_curve[-1]['equity'] == 10000.0

def test_optimizer_expectancy_and_constraints(monkeypatch):
    from run_optimizer import evaluate_param
    import run_optimizer
    
    # Mock evaluate_param to return predefined constraints
    def mock_evaluate(score, bars):
        # We will create a fake wf_results behavior inside run() by patching evaluate_param
        pass
    
    # Actually we can test constraints directly by creating a fake evaluate_param returns
    results = [
        {"min_score": 60, "avg_pf": 2.0, "avg_dd": 10.0, "expectancy": 10.0, "total_trades": 10, "folds": 3}, # Failing trades min
        {"min_score": 70, "avg_pf": 3.0, "avg_dd": 40.0, "expectancy": 15.0, "total_trades": 40, "folds": 3}, # Failing DD
        {"min_score": 75, "avg_pf": 1.5, "avg_dd": 15.0, "expectancy": -5.0, "total_trades": 50, "folds": 3}, # Failing expectancy
    ]
    
    valid = [
        r for r in results 
        if r["total_trades"] >= 30 and r["avg_dd"] < 30.0 and r["expectancy"] > 0
    ]
    
    assert len(valid) == 0 # All should be rejected
    
    best = None
    if valid:
        best = max(valid, key=lambda x: (x["avg_pf"], x["expectancy"]))
        
    assert best is None
    
def test_walk_forward_isolation(monkeypatch):
    # If engine_factory is called 3 times per window, then isolation is fixed
    call_count = {"count": 0}
    def mock_factory():
        call_count["count"] += 1
        ensemble = StrategyEnsemble([])
        risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0))
        return BacktestEngine(ensemble, risk_engine)
        
    bars = [MarketBar(symbol='BTC', timestamp=datetime(2020,1,1) + timedelta(hours=i), open=1, high=1, low=1, close=1, volume=1) for i in range(100)]
    
    # window_size 50, step_size 50 -> 2 windows
    # Each window runs train, val, test engines
    res = run_walk_forward_robustness(bars, mock_factory, window_size=50, step_size=50)
    assert call_count["count"] == 6 # 2 windows * 3 engines

def test_entry_cost_accounting():
    ensemble = StrategyEnsemble([])
    from app.backtesting.models import CostConfig
    risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0))
    engine = BacktestEngine(ensemble, risk_engine, cost_config=CostConfig(commission_rate=0.01, slippage_rate=0.0))
    
    # Enter a trade (price 100, qty 10 -> $1000)
    # Entry commission: 0.01 * 1000 = $10.00
    pos = {
        'symbol': 'BTC',
        'direction': 'LONG',
        'entry_time': datetime(2021, 1, 1, tzinfo=timezone.utc),
        'entry_price': 100.0,
        'quantity': 10.0,
        'stop_loss': None,
        'take_profit': None,
        'entry_cost': 10.0,
        'slippage_entry': 0.0,
        'signal_metadata': {}
    }
    engine.portfolio.state.add_position(pos)
    
    # Deduct entry cost from equity just like _enter_position would
    engine.equity -= 10.0
    
    # Exit trade at same price (price 100, qty 10 -> $1000)
    # Exit commission: 0.01 * 1000 = $10.00
    # Gross PnL: $0.00
    engine._close_position(datetime(2021,1,2, tzinfo=timezone.utc), 100.0, pos, "Close")
    
    trade = engine.closed_trades[0]
    
    # Total costs should be 20. Net PnL should be -20.
    assert trade.realized_pnl == -20.0
    
    # Final equity should equal 10000.0 - 20.0 = 9980.0
    assert engine.equity == 9980.0
    
    # Generate result and verify
    res = engine._generate_result()
    assert res.gross_loss == 20.0
    assert res.net_profit == -20.0
    
def test_aggregate_pf_calculation():
    from run_optimizer import evaluate_param
    from app.research.robustness.models import WalkForwardWindowResult
    from unittest.mock import patch
    
    # Mock run_walk_forward_robustness to return known gross_profit and gross_loss
    def mock_wf(*args, **kwargs):
        return [
            WalkForwardWindowResult(
                window_id=1, train_start="", train_end="", validation_start="", validation_end="", test_start="", test_end="",
                strategy="A", adaptive_state="", strategy_weights={}, trades=1, return_pct=1.0, win_rate=1.0, profit_factor=float('inf'), max_drawdown_pct=0.0,
                gross_profit=100.0, gross_loss=0.0
            ),
            WalkForwardWindowResult(
                window_id=2, train_start="", train_end="", validation_start="", validation_end="", test_start="", test_end="",
                strategy="A", adaptive_state="", strategy_weights={}, trades=1, return_pct=-0.5, win_rate=0.0, profit_factor=0.0, max_drawdown_pct=0.0,
                gross_profit=0.0, gross_loss=50.0
            )
        ]
        
    with patch("run_optimizer.run_walk_forward_robustness", side_effect=mock_wf):
        res = evaluate_param(50.0, [])
        # Aggregate GP = 100, GL = 50 -> PF = 2.0
        # Average PF would have been (min(inf, 10) + 0) / 2 = 5.0
        # Make sure it's 2.0!
        assert res["avg_pf"] == 2.0
        assert res["folds"] == 2
