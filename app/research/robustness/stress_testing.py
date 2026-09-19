from typing import Callable, List
from app.backtesting.engine import BacktestEngine
from app.core.models import MarketBar
from app.backtesting.models import CostConfig
from app.research.robustness.models import CostStressScenario

def run_cost_stress_test(
    bars: List[MarketBar],
    engine_factory: Callable[[CostConfig], BacktestEngine],
    multipliers: List[float] = [1.0, 2.0, 3.0, 5.0]
) -> List[CostStressScenario]:
    results = []
    
    baseline_return = None
    
    for mult in multipliers:
        cost = CostConfig(
            commission_rate=0.001 * mult,
            slippage_rate=0.001 * mult
        )
        engine = engine_factory(cost)
        res = engine.run(bars)
        
        if mult == 1.0:
            baseline_return = res.total_return_pct
            
        degradation = 0.0
        if baseline_return is not None and baseline_return != 0:
            degradation = ((baseline_return - res.total_return_pct) / abs(baseline_return)) * 100
        
        results.append(CostStressScenario(
            multiplier=mult,
            total_trades=res.number_of_trades,
            return_pct=res.total_return_pct,
            win_rate=res.win_rate,
            profit_factor=res.profit_factor,
            max_drawdown_pct=res.max_drawdown_pct,
            degradation_pct=degradation
        ))
        
    return results
