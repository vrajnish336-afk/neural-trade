import pytest
from app.backtesting.engine import BacktestEngine
from app.risk.portfolio import PortfolioRiskConfig
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from tests.unit.test_strategies import generate_bars

def test_backtest_reproducibility():
    bars = generate_bars([10, 10, 10, 10, 20, 30, 25, 20, 15, 10, 5]*2) # 22 bars
    
    # Run 1
    ensemble1 = StrategyEnsemble([TrendFollowingStrategy(fast_period=2, slow_period=3)], min_score=0.0)
    risk1 = RiskEngine(PortfolioRiskLimits(1000), 0.1)
    engine1 = BacktestEngine(ensemble1, risk1, initial_capital=1000)
    res1 = engine1.run(bars)
    
    # Run 2
    ensemble2 = StrategyEnsemble([TrendFollowingStrategy(fast_period=2, slow_period=3)], min_score=0.0)
    risk2 = RiskEngine(PortfolioRiskLimits(1000), 0.1)
    engine2 = BacktestEngine(ensemble2, risk2, initial_capital=1000)
    res2 = engine2.run(bars)
    
    assert res1.final_equity == res2.final_equity
    assert res1.number_of_trades == res2.number_of_trades
    assert res1.total_return_pct == res2.total_return_pct
    
    # Should be deterministic
    if res1.number_of_trades > 0:
        assert res1.trades[0].entry_price == res2.trades[0].entry_price
