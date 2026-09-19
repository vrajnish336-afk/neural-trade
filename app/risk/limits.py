from typing import List
from app.backtesting.models import BacktestTrade

class PortfolioRiskLimits:
    """
    Tracks and enforces portfolio-level risk limits.
    """
    def __init__(self, initial_equity: float, max_positions: int = 5, max_exposure_pct: float = 1.0, daily_loss_limit_pct: float = 0.05, loss_streak_threshold: int = 3, cooldown_bars: int = 5, max_drawdown_halt_pct: float = 20.0):
        self.initial_equity = initial_equity
        self.max_positions = max_positions
        self.max_exposure_pct = max_exposure_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.loss_streak_threshold = loss_streak_threshold
        self.cooldown_bars = cooldown_bars
        self.max_drawdown_halt_pct = max_drawdown_halt_pct  # % — e.g. 20.0 means halt at 20% drawdown
        
        self.loss_streak = 0
        self.daily_loss = 0.0
        self.cooldown_remaining = 0
        
    def step_bar(self) -> None:
        """Called by the engine on every new bar to decrease cooldown."""
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            
    def update_from_closed_trade(self, trade: BacktestTrade) -> None:
        if trade.realized_pnl < 0:
            self.loss_streak += 1
            self.daily_loss += abs(trade.realized_pnl)
            
            if self.loss_streak >= self.loss_streak_threshold:
                self.cooldown_remaining = self.cooldown_bars
        else:
            self.loss_streak = 0
            
    def reset_daily_loss(self) -> None:
        self.daily_loss = 0.0
        
    def can_open_new_position(self, current_positions_count: int, current_exposure: float, current_equity: float) -> tuple[bool, str, str]:
        """
        Evaluates whether a new position can be opened based on risk limits.
        Returns: (approved, reason, limit_name)
        """
        if self.cooldown_remaining > 0:
            return False, f"cooldown active for {self.cooldown_remaining} more bars.", "Cooldown"
            
        if current_positions_count >= self.max_positions:
            return False, "maximum position count reached.", "Max Positions"
            
        if (current_exposure / current_equity) >= self.max_exposure_pct:
            return False, "maximum exposure limit reached.", "Max Exposure"
            
        # If today's loss has exceeded the daily limit
        max_allowed_loss = current_equity * self.daily_loss_limit_pct
        if self.daily_loss >= max_allowed_loss:
            return False, "maximum daily loss limit reached.", "Daily Loss"
            
        return True, "", ""
