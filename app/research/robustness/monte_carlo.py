import random
import numpy as np
from typing import List
from app.backtesting.models import BacktestTrade
from app.research.robustness.models import MonteCarloRobustnessResult

def run_monte_carlo_robustness(
    trades: List[BacktestTrade], 
    initial_capital: float, 
    simulations: int = 1000, 
    seed: int = 42
) -> MonteCarloRobustnessResult:
    """
    Deterministically reshuffles historical trade outcomes to estimate order-sensitivity.
    This does NOT predict future market performance.
    """
    if not trades:
        return MonteCarloRobustnessResult(
            simulations=0,
            median_return_pct=0.0, p05_return_pct=0.0, p25_return_pct=0.0, p75_return_pct=0.0, p95_return_pct=0.0,
            median_drawdown_pct=0.0, p95_drawdown_pct=0.0, worst_drawdown_pct=0.0
        )
        
    random.seed(seed)
    np.random.seed(seed)
    
    pnls = [t.realized_pnl for t in trades]
    returns = []
    drawdowns = []
    
    for _ in range(simulations):
        shuffled = pnls.copy()
        random.shuffle(shuffled)
        
        eq = initial_capital
        peak = eq
        max_dd = 0.0
        
        for pnl in shuffled:
            eq += pnl
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                
        ret_pct = ((eq - initial_capital) / initial_capital) * 100
        returns.append(ret_pct)
        drawdowns.append(max_dd)
        
    return MonteCarloRobustnessResult(
        simulations=simulations,
        median_return_pct=float(np.median(returns)),
        p05_return_pct=float(np.percentile(returns, 5)),
        p25_return_pct=float(np.percentile(returns, 25)),
        p75_return_pct=float(np.percentile(returns, 75)),
        p95_return_pct=float(np.percentile(returns, 95)),
        median_drawdown_pct=float(np.median(drawdowns)),
        p95_drawdown_pct=float(np.percentile(drawdowns, 95)),
        worst_drawdown_pct=float(max(drawdowns))
    )

def run_sequence_risk_stress(trades: List[BacktestTrade], initial_capital: float, simulations: int = 1000, seed: int = 42) -> dict:
    """
    Historical sequence stress test ONLY.
    Calculates how often a reshuffled sequence crosses specified drawdown thresholds.
    """
    if not trades:
        return {}
        
    random.seed(seed)
    
    pnls = [t.realized_pnl for t in trades]
    thresholds = [10.0, 20.0, 30.0, 50.0]
    crossing_counts = {t: 0 for t in thresholds}
    
    min_equities = []
    
    for _ in range(simulations):
        shuffled = pnls.copy()
        random.shuffle(shuffled)
        
        eq = initial_capital
        peak = eq
        max_dd = 0.0
        min_eq = initial_capital
        
        for pnl in shuffled:
            eq += pnl
            if eq < min_eq:
                min_eq = eq
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                
        min_equities.append(min_eq)
        
        for t in thresholds:
            if max_dd >= t:
                crossing_counts[t] += 1
                
    results = {
        'simulations': simulations,
        'thresholds': {}
    }
    for t in thresholds:
        results['thresholds'][f'{int(t)}%'] = {
            'count': crossing_counts[t],
            'percentage': (crossing_counts[t] / simulations) * 100.0
        }
        
    import numpy as np
    results['median_min_equity'] = float(np.median(min_equities))
    results['worst_simulated_equity'] = float(min(min_equities))
    
    return results
