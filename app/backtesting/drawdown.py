from typing import List, Dict, Optional, Tuple
from datetime import datetime

def calculate_extended_drawdown_metrics(equity_curve: List[Dict]) -> Dict:
    """
    Calculates detailed drawdown metrics.
    Expects equity_curve items to have 'timestamp', 'equity', 'exposure'
    """
    if not equity_curve:
        return {}
        
    peak = equity_curve[0]['equity']
    peak_date = equity_curve[0]['timestamp']
    max_dd_pct = 0.0
    current_dd_start = None
    
    longest_dd_duration = 0
    max_recovery_time = 0
    
    current_duration = 0
    
    for pt in equity_curve:
        eq = pt['equity']
        dt = pt['timestamp']
        
        if eq >= peak:
            if current_dd_start is not None:
                # Recovery complete
                recovery_time = 0 # Cannot subtract ISO strings easily without parsing, let's keep it simple as periods
                if current_duration > max_recovery_time:
                    max_recovery_time = current_duration
            peak = eq
            peak_date = dt
            current_dd_start = None
            current_duration = 0
        else:
            if current_dd_start is None:
                current_dd_start = dt
                current_duration = 1
            else:
                current_duration += 1
                
            dd_pct = (peak - eq) / peak
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                
            if current_duration > longest_dd_duration:
                longest_dd_duration = current_duration
                
    return {
        'max_drawdown_pct': max_dd_pct * 100.0,
        'longest_drawdown_periods': longest_dd_duration,
        'max_recovery_periods': max_recovery_time
    }

def calculate_consecutive_losses(trades: List['BacktestTrade']) -> int:
    max_streak = 0
    current_streak = 0
    for t in trades:
        if t.realized_pnl < 0:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            current_streak = 0
    return max_streak
