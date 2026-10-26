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
    def __init__(self, current_cash: float = 0.0):
        self.open_positions: List[Dict] = []
        self.current_cash: float = current_cash
        
    def add_position(self, pos: Dict):
        self.open_positions.append(pos)
        
    def remove_position(self, symbol: str, direction: str):
        for i, pos in enumerate(self.open_positions):
            if pos['symbol'] == symbol and pos['direction'] == direction:
                self.open_positions.pop(i)
                break

    def calculate_unrealized_pnl(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculates the combined unrealized PnL of all currently open positions.
        Uses current_prices[symbol] if provided, else pos['current_price'], else pos['entry_price'].
        """
        prices = current_prices or {}
        total_pnl = 0.0
        for pos in self.open_positions:
            sym = pos.get('symbol')
            price = prices.get(sym) if sym in prices else pos.get('current_price')
            if price is None:
                price = pos.get('entry_price', 0.0)
                
            qty = float(pos.get('quantity', 0.0))
            entry = float(pos.get('entry_price', 0.0))
            direction = pos.get('direction', 'LONG')
            
            if price > 0 and qty > 0 and entry > 0:
                if direction == 'LONG':
                    total_pnl += (price - entry) * qty
                elif direction == 'SHORT':
                    total_pnl += (entry - price) * qty
        return total_pnl

    @property
    def current_equity(self) -> float:
        """
        True dynamic equity: Realized Cash + Combined unrealized PnL of all currently open positions.
        """
        return self.current_cash + self.calculate_unrealized_pnl()

    def get_dynamic_equity(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculates true dynamic equity given live market prices.
        """
        return self.current_cash + self.calculate_unrealized_pnl(current_prices)

class PortfolioRiskManager:
    """
    Manages portfolio-level risk limits for multi-symbol, multi-strategy backtesting.
    """
    def __init__(self, config: PortfolioRiskConfig):
        self.config = config
        self.state = PortfolioState()
        
    def can_open_position(self, signal: TradingSignal, position_size: float, current_equity: float, current_prices: Optional[Dict[str, float]] = None) -> tuple[bool, str, str]:
        """
        Check if opening a position complies with portfolio risk limits.
        Evaluates against true dynamic equity (including open losses).
        Returns: (approved, reason, limit_name)
        """
        if len(self.state.open_positions) >= self.config.max_concurrent_positions:
            return False, "Maximum concurrent positions reached.", "MAX_CONCURRENT_POSITIONS"
            
        position_value = position_size * signal.entry_price

        # Evaluate against dynamic equity if prices or open positions exist
        eval_equity = current_equity
        if current_prices or (self.state.open_positions and self.state.current_cash > 0):
            eval_equity = self.state.get_dynamic_equity(current_prices) if self.state.current_cash > 0 else (current_equity + self.state.calculate_unrealized_pnl(current_prices))

        if eval_equity <= 0:
            return False, "Portfolio dynamic equity is depleted or negative.", "PORTFOLIO_EXPOSURE_LIMIT"
        
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
        
        if new_gross / eval_equity > self.config.max_gross_exposure_pct:
            return False, "Portfolio gross exposure limit exceeded.", "PORTFOLIO_EXPOSURE_LIMIT"
            
        if abs(new_net) / eval_equity > self.config.max_net_exposure_pct:
            return False, "Portfolio net exposure limit exceeded.", "PORTFOLIO_EXPOSURE_LIMIT"
            
        if new_symbol_exp / eval_equity > self.config.max_symbol_exposure_pct:
            return False, f"Symbol exposure limit exceeded for {signal.symbol}.", "SYMBOL_EXPOSURE_LIMIT"
            
        if new_strategy_exp / eval_equity > self.config.max_strategy_exposure_pct:
            return False, f"Strategy exposure limit exceeded for {signal.strategy}.", "STRATEGY_EXPOSURE_LIMIT"
            
        if new_aggregate_risk / eval_equity > self.config.max_aggregate_stop_risk_pct:
            return False, "Aggregate stop risk limit exceeded.", "AGGREGATE_RISK_LIMIT"
            
        return True, "", ""
