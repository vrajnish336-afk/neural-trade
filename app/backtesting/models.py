from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class BacktestTrade(BaseModel):
    """Represents a simulated closed trade within a backtest."""
    symbol: str
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: float
    entry_cost: float = 0.0
    exit_cost: float = 0.0
    slippage_cost: float = 0.0
    realized_pnl: float
    exit_reason: str
    regime: Optional[str] = None
    score: Optional[float] = None
    strategies: Optional[str] = None
    risk_reason: Optional[str] = None
    sentiment_label: Optional[str] = None
    anomaly_flags: Optional[str] = None
    fakeout_risk: Optional[str] = None

class BacktestResult(BaseModel):
    """Summary metrics of a completed backtest."""
    initial_capital: float
    final_equity: float
    total_return_pct: float
    number_of_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    max_drawdown_pct: float
    average_trade_result: float
    profit_factor: float
    average_holding_period_hours: float
    unresolved_positions_count: int = 0
    unrealized_mtm: float = 0.0
    trades: List[BacktestTrade] = Field(default_factory=list)
    equity_curve: List[dict] = Field(default_factory=list)
    telemetry_snapshot: Optional[dict] = None

    @property
    def post_cost_gross_profit(self) -> float:
        """Post-cost gross profit (sum of winning trades' realized PnL after costs)."""
        return self.gross_profit

    @property
    def post_cost_gross_loss(self) -> float:
        """Post-cost gross loss (sum of losing trades' absolute realized PnL after costs)."""
        return self.gross_loss

    @property
    def post_cost_profit_factor(self) -> float:
        """Post-cost profit factor (gross_profit / gross_loss)."""
        return self.profit_factor

    @property
    def total_costs(self) -> float:
        """Total execution costs (entry fees + exit fees + slippage) across all trades."""
        return sum(getattr(t, 'entry_cost', 0.0) + getattr(t, 'exit_cost', 0.0) + getattr(t, 'slippage_cost', 0.0) for t in self.trades)

    @property
    def pre_cost_gross_profit(self) -> float:
        """Raw pre-cost gross profit before commission and slippage deductions."""
        raw_pnls = [
            t.realized_pnl + getattr(t, 'entry_cost', 0.0) + getattr(t, 'exit_cost', 0.0) + getattr(t, 'slippage_cost', 0.0)
            for t in self.trades
        ]
        return sum(p for p in raw_pnls if p > 0)

    @property
    def pre_cost_gross_loss(self) -> float:
        """Raw pre-cost gross loss before commission and slippage deductions."""
        raw_pnls = [
            t.realized_pnl + getattr(t, 'entry_cost', 0.0) + getattr(t, 'exit_cost', 0.0) + getattr(t, 'slippage_cost', 0.0)
            for t in self.trades
        ]
        return abs(sum(p for p in raw_pnls if p <= 0))

    @property
    def pre_cost_profit_factor(self) -> float:
        """Raw pre-cost profit factor (pre-cost gross profit / pre-cost gross loss)."""
        gl = self.pre_cost_gross_loss
        gp = self.pre_cost_gross_profit
        if gl > 0:
            return gp / gl
        return float('inf') if gp > 0 else 0.0
    
class CostConfig(BaseModel):
    """Configuration for simulated costs."""
    commission_rate: float = 0.0
    slippage_rate: float = 0.0
    
class ExecutionAssumptions:
    BASELINE = CostConfig(commission_rate=0.001, slippage_rate=0.001)
    SLIPPAGE_2X = CostConfig(commission_rate=0.001, slippage_rate=0.002)
    SLIPPAGE_3X = CostConfig(commission_rate=0.001, slippage_rate=0.003)
    SLIPPAGE_5X = CostConfig(commission_rate=0.001, slippage_rate=0.005)
