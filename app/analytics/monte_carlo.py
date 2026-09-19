import random
import numpy as np
from typing import List
from app.backtesting.models import BacktestTrade
from app.analytics.models import MonteCarloResult
from app.analytics.performance import calculate_equity_metrics

def run_monte_carlo_resampling(trades: List[BacktestTrade], initial_capital: float, simulations: int = 1000, seed: int = 42) -> MonteCarloResult:
    """
    Deterministically reshuffles historical trade outcomes to estimate order-sensitivity.
    This does NOT predict future market performance.
    """
    if not trades:
        return MonteCarloResult(simulations=0, median_drawdown_pct=0.0, percentile_95_drawdown_pct=0.0, max_losing_streak_95th=0)
        
    random.seed(seed)
    np.random.seed(seed)
    
    # We only care about the sequence of PnLs
    pnls = [t.realized_pnl for t in trades]
    
    max_drawdowns = []
    max_losing_streaks = []
    
    for _ in range(simulations):
        shuffled = pnls.copy()
        random.shuffle(shuffled)
        
        # Build synthetic equity curve
        eq = initial_capital
        eq_curve = [{'equity': eq}]
        
        current_loss_streak = 0
        max_streak = 0
        
        for pnl in shuffled:
            eq += pnl
            eq_curve.append({'equity': eq})
            
            if pnl <= 0:
                current_loss_streak += 1
                max_streak = max(max_streak, current_loss_streak)
            else:
                current_loss_streak = 0
                
        metrics = calculate_equity_metrics(eq_curve, initial_capital)
        max_drawdowns.append(metrics.max_drawdown_pct)
        max_losing_streaks.append(max_streak)
        
    return MonteCarloResult(
        simulations=simulations,
        median_drawdown_pct=float(np.median(max_drawdowns)),
        percentile_95_drawdown_pct=float(np.percentile(max_drawdowns, 95)),
        max_losing_streak_95th=int(np.percentile(max_losing_streaks, 95))
    )
