import logging

logger = logging.getLogger(__name__)

def calculate_fixed_percentage_risk(equity: float, risk_percentage: float) -> float:
    """Calculates risk amount based on a fixed percentage of equity."""
    return max(0.0, equity * risk_percentage)

def calculate_position_size_by_stop_distance(risk_amount: float, entry_price: float, stop_loss: float) -> float:
    """
    Calculates the quantity (position size) such that if the stop loss is hit,
    the loss equals the risk_amount.
    """
    if entry_price <= 0 or stop_loss <= 0:
        return 0.0
        
    distance = abs(entry_price - stop_loss)
    if distance == 0:
        return 0.0
        
    return risk_amount / distance

def calculate_atr_stop(direction: str, entry_price: float, atr_value: float, multiplier: float = 2.0) -> float:
    """
    Calculates a volatility-based stop loss using ATR.
    LONG: stop = entry - ATR * multiplier
    SHORT: stop = entry + ATR * multiplier
    """
    if direction == "LONG":
        return max(0.0001, entry_price - (atr_value * multiplier))
    elif direction == "SHORT":
        return entry_price + (atr_value * multiplier)
    else:
        raise ValueError("Invalid direction")
