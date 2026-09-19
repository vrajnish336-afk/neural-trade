import pytest
from app.research.robustness.walk_forward import run_walk_forward_robustness
from app.core.models import MarketBar
from datetime import datetime, timezone, timedelta
from app.backtesting.engine import BacktestEngine
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

def test_walk_forward_boundaries_are_distinct():
    bars = [
        MarketBar(symbol='TEST', timestamp=datetime(2022, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), open=100.0, high=101.0, low=99.0, close=100.5, volume=1000)
        for i in range(10)
    ]
    
    def engine_factory():
        ensemble = StrategyEnsemble([TrendFollowingStrategy()])
        risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0), risk_per_trade_pct=0.1)
        eng = BacktestEngine(ensemble, risk_engine)
        return eng
        
    results = run_walk_forward_robustness(bars, engine_factory, window_size=6, step_size=2)
    
    # We should have valid out-of-sample slices
    res1 = results[0]
    assert res1.test_start != res1.test_end
    # Ensure test start matches validation end
    assert res1.validation_end == res1.test_start

