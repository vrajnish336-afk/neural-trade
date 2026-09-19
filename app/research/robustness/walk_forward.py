from typing import Callable, List
from app.backtesting.engine import BacktestEngine
from app.core.models import MarketBar
from app.research.robustness.models import WalkForwardWindowResult

def run_walk_forward_robustness(
    bars: List[MarketBar],
    engine_factory: Callable[[], BacktestEngine],
    window_size: int = 500,
    step_size: int = 250
) -> List[WalkForwardWindowResult]:
    results = []
    total_bars = len(bars)
    start_idx = 0
    window_id = 1
    
    while start_idx + window_size <= total_bars:
        window_bars = bars[start_idx : start_idx + window_size]
        
        train_end_idx = int(window_size * 0.5)
        val_end_idx = int(window_size * 0.75)
        
        train_bars = window_bars[:train_end_idx]
        val_bars = window_bars[train_end_idx:val_end_idx]
        test_bars = window_bars[val_end_idx:]
        
        test_start = str(test_bars[0].timestamp)
        test_end = str(test_bars[-1].timestamp)
        
        engine = engine_factory()
        res = engine.run(window_bars)
        
        # Only take trades that happen in the out-of-sample period (test_start to test_end)
        from dateutil.parser import parse
        t_start = parse(test_start)
        oos_trades = [t for t in engine.closed_trades if t.entry_time >= t_start]
        
        return_pct = 0.0
        profit_factor = 0.0
        win_rate = 0.0
        
        if oos_trades:
            wins = [t for t in oos_trades if t.realized_pnl > 0]
            gross_profit = sum(t.realized_pnl for t in wins)
            gross_loss = sum(abs(t.realized_pnl) for t in oos_trades if t.realized_pnl < 0)
            
            win_rate = len(wins) / len(oos_trades)
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
            
            # approximate return
            return_pct = sum(t.realized_pnl for t in oos_trades) / 10000.0
        
        results.append(WalkForwardWindowResult(
            window_id=window_id,
            train_start=str(train_bars[0].timestamp),
            train_end=str(train_bars[-1].timestamp),
            validation_start=str(val_bars[0].timestamp),
            validation_end=test_start,
            test_start=test_start,
            test_end=test_end,
            strategy='Adaptive',
            adaptive_state='Varies',
            strategy_weights={},
            trades=len(oos_trades),
            return_pct=return_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown_pct=res.max_drawdown_pct
        ))
        start_idx += step_size
        window_id += 1
    return results
