from typing import Tuple
from app.backtesting.models import CostConfig

def apply_entry_costs(price: float, quantity: float, direction: str, cost_config: CostConfig) -> Tuple[float, float, float]:
    """
    Simulates applying costs to an entry order.
    Returns: (actual_execution_price, commission_cost, slippage_cost)
    
    A LONG entry suffers slippage by buying at a higher price.
    A SHORT entry suffers slippage by selling at a lower price.
    """
    trade_value = price * quantity
    commission = trade_value * cost_config.commission_rate
    slippage_cost = trade_value * cost_config.slippage_rate
    
    # Adjust price based on direction for realistic slippage simulation
    if direction == "LONG":
        actual_price = price * (1 + cost_config.slippage_rate)
    else:
        actual_price = price * (1 - cost_config.slippage_rate)
        
    return actual_price, commission, slippage_cost

def apply_exit_costs(price: float, quantity: float, direction: str, cost_config: CostConfig) -> Tuple[float, float, float]:
    """
    Simulates applying costs to an exit order.
    Returns: (actual_execution_price, commission_cost, slippage_cost)
    
    Exiting a LONG means selling, so slippage reduces the price.
    Exiting a SHORT means buying, so slippage increases the price.
    """
    trade_value = price * quantity
    commission = trade_value * cost_config.commission_rate
    slippage_cost = trade_value * cost_config.slippage_rate
    
    if direction == "LONG":
        actual_price = price * (1 - cost_config.slippage_rate)
    else:
        actual_price = price * (1 + cost_config.slippage_rate)
        
    return actual_price, commission, slippage_cost
