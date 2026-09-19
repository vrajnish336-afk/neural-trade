from typing import List
from app.backtesting.models import BacktestTrade

def calculate_drawdown(equity_curve: List[float]) -> float:
    """Calculates maximum drawdown percentage from an equity curve."""
    if not equity_curve:
        return 0.0
        
    peak = equity_curve[0]
    max_dd = 0.0
    
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd
            
    return max_dd * 100.0

def calculate_profit_factor(gross_profit: float, gross_loss: float) -> float:
    """Calculates profit factor (gross profit / gross loss)."""
    if gross_loss == 0.0:
        return float('inf') if gross_profit > 0 else 0.0
    return gross_profit / gross_loss
