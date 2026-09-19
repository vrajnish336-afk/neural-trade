import pytest
import copy
from datetime import datetime, timezone
from app.research.dataset import generate_synthetic_data
from app.strategies.breakout import BreakoutStrategy
from app.backtesting.models import CostConfig
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.backtesting.engine import BacktestEngine
from app.risk.portfolio import PortfolioRiskConfig
from app.strategies.ensemble import StrategyEnsemble
from app.news.provider import FixtureNewsProvider
from app.services.intelligence import IntelligenceService
from app.config import config

def test_no_lookahead_bias():
    """
    Ensures that modifying a future candle does not alter the signal or state generated at time T.
    A proper test feeds the entire series to the engine and compares the trades generated up to T.
    """
    bars = generate_synthetic_data(["TEST"], num_bars=100, seed=42)["TEST"]
    
    # 1. Run Baseline on all 100 bars
    engine_base = BacktestEngine(
        ensemble=StrategyEnsemble([BreakoutStrategy()], min_score=0.0),
        risk_engine=RiskEngine(PortfolioRiskLimits(10000.0)),
        intelligence_service=IntelligenceService(FixtureNewsProvider(), config),
        initial_capital=10000.0,
        cost_config=CostConfig()
    )
    engine_base.run(bars)
    
    baseline_trades = [t for t in engine_base.closed_trades if t.entry_time <= bars[50].timestamp]
    
    # 2. Corrupt future data (bars 51-99)
    corrupted_bars = copy.deepcopy(bars)
    for i in range(51, 100):
        corrupted_bars[i].close = 999999.0
        corrupted_bars[i].volume = 999999.0
        corrupted_bars[i].high = 999999.0
        
    # 3. Run again on all 100 corrupted bars
    engine_test = BacktestEngine(
        ensemble=StrategyEnsemble([BreakoutStrategy()], min_score=0.0),
        risk_engine=RiskEngine(PortfolioRiskLimits(10000.0)),
        intelligence_service=IntelligenceService(FixtureNewsProvider(), config),
        initial_capital=10000.0,
        cost_config=CostConfig()
    )
    engine_test.run(corrupted_bars)
    
    test_trades = [t for t in engine_test.closed_trades if t.entry_time <= corrupted_bars[50].timestamp]
    
    # The trades entered up to T=50 must be exactly identical, even though the engine processed the future bars.
    # Note: exit times/prices might differ if the position was held past T=50, 
    # but the ENTRY logic and all decisions up to T=50 must be unaffected.
    
    # We only check entry characteristics to prove no lookahead bias at entry time.
    assert len(baseline_trades) == len(test_trades), "Lookahead bias: Number of trades before T=50 changed!"
    
    for b_trade, t_trade in zip(baseline_trades, test_trades):
        assert b_trade.entry_time == t_trade.entry_time
        assert b_trade.entry_price == t_trade.entry_price
        assert b_trade.direction == t_trade.direction
        assert b_trade.quantity == t_trade.quantity
