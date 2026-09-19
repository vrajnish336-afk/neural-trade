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
    trades: List[BacktestTrade] = Field(default_factory=list)
    equity_curve: List[dict] = Field(default_factory=list)
    telemetry_snapshot: Optional[dict] = None
    
class CostConfig(BaseModel):
    """Configuration for simulated costs."""
    commission_rate: float = 0.0
    slippage_rate: float = 0.0
    
class ExecutionAssumptions:
    BASELINE = CostConfig(commission_rate=0.001, slippage_rate=0.001)
    SLIPPAGE_2X = CostConfig(commission_rate=0.001, slippage_rate=0.002)
    SLIPPAGE_3X = CostConfig(commission_rate=0.001, slippage_rate=0.003)
    SLIPPAGE_5X = CostConfig(commission_rate=0.001, slippage_rate=0.005)
