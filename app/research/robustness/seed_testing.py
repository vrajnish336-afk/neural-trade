from typing import Callable, List
from app.backtesting.engine import BacktestEngine
from app.research.dataset import generate_synthetic_data
from app.research.robustness.models import SeedTestResult
from app.core.models import MarketBar

def run_seed_robustness(
    symbol: str,
    engine_factory: Callable[[], BacktestEngine],
    seeds: List[int] = [101, 202, 303, 404, 505],
    num_bars: int = 1000
) -> List[SeedTestResult]:
    """
    Evaluates strategy consistency across differently seeded synthetic datasets.
    """
    results = []
    
    for s in seeds:
        bars = generate_synthetic_data([symbol], num_bars=num_bars, seed=s)[symbol]
        engine = engine_factory()
        res = engine.run(bars)
        
        results.append(SeedTestResult(
            seed=s,
            trades=res.number_of_trades,
            return_pct=res.total_return_pct,
            win_rate=res.win_rate,
            profit_factor=res.profit_factor,
            max_drawdown_pct=res.max_drawdown_pct
        ))
        
    return results
