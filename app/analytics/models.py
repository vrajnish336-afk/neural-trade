from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class TradeMetrics(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    total_commission: float = 0.0
    total_slippage: float = 0.0
    average_pnl: float
    average_win: float
    average_loss: float
    profit_factor: float
    largest_win: float
    largest_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    average_holding_hours: float

    @property
    def post_cost_profit_factor(self) -> float:
        """Explicit label: post-cost profit factor."""
        return self.profit_factor

    @property
    def post_cost_net_pnl(self) -> float:
        """Explicit label: net PnL after commissions and slippage."""
        return self.net_pnl

    @property
    def total_execution_costs(self) -> float:
        """Total execution costs (commissions + slippage)."""
        return self.total_commission + self.total_slippage

    @property
    def pre_cost_gross_pnl(self) -> float:
        """Explicit label: gross PnL prior to commission deductions."""
        return self.gross_pnl

class EquityMetrics(BaseModel):
    initial_capital: float
    final_equity: float
    absolute_pnl: float
    total_return_pct: float
    max_drawdown_pct: float
    max_drawdown_amount: float
    average_drawdown_pct: float
    time_in_drawdown_pct: float
    recovery_periods: int

class AttributionMetrics(BaseModel):
    category: str
    label: str
    sample_size: int
    win_rate: float
    total_pnl: float
    average_pnl: float
    profit_factor: float

class FailureFinding(BaseModel):
    finding: str
    sample_size: int
    metric: str
    timeframe: Optional[str] = None
    symbol: Optional[str] = None

class StrategyComparison(BaseModel):
    strategy: str
    trade_count: int
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    average_trade: float
    sample_size_warning: bool

class WalkForwardWindowResult(BaseModel):
    window_name: str
    train_return: float
    train_drawdown: float
    test_return: float
    test_drawdown: float
    degradation_pct: float

class WalkForwardResult(BaseModel):
    windows: List[WalkForwardWindowResult]
    average_degradation: float

class ParameterSensitivityResult(BaseModel):
    parameter_set: str
    trade_count: int
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float

class MonteCarloResult(BaseModel):
    simulations: int
    median_drawdown_pct: float
    percentile_95_drawdown_pct: float
    max_losing_streak_95th: int

class FullAnalyticsReport(BaseModel):
    backtest_id: str
    trade_metrics: TradeMetrics
    equity_metrics: EquityMetrics
    strategy_attribution: List[AttributionMetrics]
    regime_attribution: List[AttributionMetrics]
    signal_bucket_attribution: List[AttributionMetrics]
    intelligence_attribution: List[AttributionMetrics]
    failure_findings: List[FailureFinding]
    strategy_comparisons: List[StrategyComparison]
    telemetry_snapshot: Optional[Dict] = None
