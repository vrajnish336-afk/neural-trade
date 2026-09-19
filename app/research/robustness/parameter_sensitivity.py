from typing import Callable, List
from app.backtesting.engine import BacktestEngine
from app.core.models import MarketBar
from app.research.robustness.models import ParameterSensitivityResult

def run_parameter_sensitivity(
    bars: List[MarketBar],
    engine_factory: Callable[[float], BacktestEngine],
    param_name: str,
    baseline_val: float,
    test_vals: List[float]
) -> List[ParameterSensitivityResult]:
    """
    Evaluates sensitivity of performance to parameter changes.
    """
    results = []
    
    for val in test_vals:
        engine = engine_factory(val)
        res = engine.run(bars)
        
        results.append(ParameterSensitivityResult(
            parameter_name=param_name,
            baseline_value=str(baseline_val),
            tested_value=str(val),
            train_result={}, # Omitted for brevity unless needed
            validation_result={},
            test_result={},
            trade_count=res.number_of_trades,
            return_pct=res.total_return_pct,
            win_rate=res.win_rate,
            profit_factor=res.profit_factor,
            max_drawdown_pct=res.max_drawdown_pct
        ))
        
    return results
