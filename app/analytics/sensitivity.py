import copy
from typing import List, Dict, Any, Type
from app.core.models import MarketBar
from app.backtesting.engine import BacktestEngine
from app.analytics.models import ParameterSensitivityResult

def run_parameter_sensitivity(
    strategy_class: Type,
    param_grid: List[Dict[str, Any]],
    bars: List[MarketBar],
    engine_factory_func: callable
) -> List[ParameterSensitivityResult]:
    """
    Evaluates a deterministic strategy over a given set of parameter configurations.
    Warning: This is for research ONLY. Overfitting historical data is a known risk.
    `engine_factory_func` must return a fresh BacktestEngine instance.
    """
    results = []
    
    for params in param_grid:
        # Instantiate strategy with new parameters
        strategy = strategy_class(**params)
        
        # Get fresh engine
        engine = engine_factory_func([strategy])
        
        # Run
        res = engine.run(bars)
        
        results.append(ParameterSensitivityResult(
            parameter_set=str(params),
            trade_count=res.number_of_trades,
            total_return_pct=res.total_return_pct,
            max_drawdown_pct=res.max_drawdown_pct,
            win_rate=res.win_rate,
            profit_factor=res.profit_factor
        ))
        
    return results
