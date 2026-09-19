import pytest
from app.backtesting.models import CostConfig
from app.research.robustness.stress_testing import run_cost_stress_test
from app.core.models import MarketBar
from datetime import datetime, timezone, timedelta
from app.backtesting.engine import BacktestEngine
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

def test_cost_multiplier_propagation():
    bars = [
        MarketBar(symbol='TEST', timestamp=datetime(2022, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), open=100.0 + i, high=101.0 + i, low=99.0 + i, close=100.5 + i, volume=1000)
        for i in range(50)
    ]
    
    configs_used = []
    
    def engine_factory(cost_config: CostConfig):
        configs_used.append(cost_config)
        ensemble = StrategyEnsemble([TrendFollowingStrategy()])
        risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0), risk_per_trade_pct=0.1)
        eng = BacktestEngine(ensemble, risk_engine, cost_config=cost_config)
        return eng
        
    results = run_cost_stress_test(bars, engine_factory, multipliers=[1.0, 2.0, 3.0])
    
    assert configs_used[0].commission_rate == 0.001
    assert configs_used[1].commission_rate == 0.002
    assert configs_used[2].commission_rate == 0.003
    
    assert configs_used[0].slippage_rate == 0.001
    assert configs_used[1].slippage_rate == 0.002
    assert configs_used[2].slippage_rate == 0.003

