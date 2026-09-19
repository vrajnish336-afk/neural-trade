from typing import List, Callable
from app.core.models import MarketBar
from app.backtesting.models import CostConfig
from app.backtesting.engine import BacktestEngine
from app.research.models import StressTestResult
import copy

def run_stress_test(
    engine_factory: Callable[[CostConfig], BacktestEngine],
    bars: List[MarketBar],
    base_cost_config: CostConfig,
    stress_condition_name: str,
    stress_multiplier: float = 2.0
) -> StressTestResult:
    """
    Runs a baseline backtest and a stress backtest (e.g., higher costs or slippage).
    """
    # 1. Baseline
    engine_base = engine_factory(base_cost_config)
    res_base = engine_base.run(bars)
    
    # 2. Stress
    stress_cost = CostConfig(
        commission_rate=base_cost_config.commission_rate * stress_multiplier,
        slippage_rate=base_cost_config.slippage_rate * stress_multiplier
    )
    engine_stress = engine_factory(stress_cost)
    res_stress = engine_stress.run(bars)
    
    degradation = res_base.total_return_pct - res_stress.total_return_pct
    
    return StressTestResult(
        condition_name=stress_condition_name,
        baseline_return=res_base.total_return_pct,
        stress_return=res_stress.total_return_pct,
        degradation_pct=degradation,
        baseline_win_rate=res_base.win_rate,
        stress_win_rate=res_stress.win_rate
    )
