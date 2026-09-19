from typing import Dict, List, Optional
from dataclasses import dataclass
from app.backtesting.models import BacktestTrade
from app.core.models import TradingSignal

@dataclass
class PortfolioRiskConfig:
    max_gross_exposure_pct: float = 2.0  # e.g., 200% of equity
    max_net_exposure_pct: float = 1.0    # e.g., 100% of equity
    max_symbol_exposure_pct: float = 0.5
    max_strategy_exposure_pct: float = 0.5
    max_concurrent_positions: int = 10
    max_aggregate_stop_risk_pct: float = 0.05 # Portfolio-wide max risk 5%
    
class PortfolioState:
    def __init__(self):
        self.open_positions: List[Dict] = []
        
    def add_position(self, pos: Dict):
        self.open_positions.append(pos)
        
    def remove_position(self, symbol: str, direction: str):
        for i, pos in enumerate(self.open_positions):
            if pos['symbol'] == symbol and pos['direction'] == direction:
                self.open_positions.pop(i)
                break

class PortfolioRiskManager:
    """
    Manages portfolio-level risk limits for multi-symbol, multi-strategy backtesting.
    """
    def __init__(self, config: PortfolioRiskConfig):
        self.config = config
        self.state = PortfolioState()
        
    def can_open_position(self, signal: TradingSignal, position_size: float, current_equity: float) -> tuple[bool, str, str]:
        """
        Check if opening a position complies with portfolio risk limits.
        Returns: (approved, reason, limit_name)
        """
        if len(self.state.open_positions) >= self.config.max_concurrent_positions:
            return False, "Maximum concurrent positions reached.", "MAX_CONCURRENT_POSITIONS"
            
        position_value = position_size * signal.entry_price
        
        # Calculate current exposures
        gross_exposure = 0.0
        net_exposure = 0.0
        symbol_exposure = 0.0
        strategy_exposure = 0.0
        aggregate_stop_risk = 0.0
        
        for pos in self.state.open_positions:
            val = pos['quantity'] * pos['entry_price']
            gross_exposure += val
            
            if pos['direction'] == 'LONG':
                net_exposure += val
            else:
                net_exposure -= val
                
            if pos['symbol'] == signal.symbol:
                symbol_exposure += val
                
            if pos['signal_metadata'].get('strategies') == signal.strategy:
                strategy_exposure += val
                
            if pos['stop_loss']:
                # Risk = absolute distance to stop loss * quantity
                risk = abs(pos['entry_price'] - pos['stop_loss']) * pos['quantity']
                aggregate_stop_risk += risk
                
        # Propose adding the new position
        new_gross = gross_exposure + position_value
        if signal.direction == 'LONG':
            new_net = net_exposure + position_value
        else:
            new_net = net_exposure - position_value
            
        new_symbol_exp = symbol_exposure + position_value
        new_strategy_exp = strategy_exposure + position_value
        
        new_risk = 0.0
        if signal.stop_loss and signal.entry_price:
            new_risk = abs(signal.entry_price - signal.stop_loss) * position_size
            
        new_aggregate_risk = aggregate_stop_risk + new_risk
        
        if new_gross / current_equity > self.config.max_gross_exposure_pct:
            return False, "Portfolio gross exposure limit exceeded.", "PORTFOLIO_EXPOSURE_LIMIT"
            
        if abs(new_net) / current_equity > self.config.max_net_exposure_pct:
            return False, "Portfolio net exposure limit exceeded.", "PORTFOLIO_EXPOSURE_LIMIT"
            
        if new_symbol_exp / current_equity > self.config.max_symbol_exposure_pct:
            return False, f"Symbol exposure limit exceeded for {signal.symbol}.", "SYMBOL_EXPOSURE_LIMIT"
            
        if new_strategy_exp / current_equity > self.config.max_strategy_exposure_pct:
            return False, f"Strategy exposure limit exceeded for {signal.strategy}.", "STRATEGY_EXPOSURE_LIMIT"
            
        if new_aggregate_risk / current_equity > self.config.max_aggregate_stop_risk_pct:
            return False, "Aggregate stop risk limit exceeded.", "AGGREGATE_RISK_LIMIT"
            
        return True, "", ""
