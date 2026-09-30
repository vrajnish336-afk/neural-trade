import logging
from typing import Optional, Tuple
from app.core.models import RiskDecision, TradingSignal
from app.risk.limits import PortfolioRiskLimits
from app.risk.position_sizing import calculate_position_size_by_stop_distance

logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Central risk evaluation logic.
    Receives a validated TradingSignal and current portfolio state,
    returns a deterministic RiskDecision.
    """
    def __init__(self, limits: PortfolioRiskLimits, risk_per_trade_pct: float = 0.01, max_position_value_pct: float = 1.0):
        self.limits = limits
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_value_pct = max_position_value_pct
        self.is_death_mode_active: bool = False
        self.death_mode_reason: Optional[str] = None
        
    def manual_reset_death_mode(self) -> None:
        """Manually resets the latched Risk-Off Death Mode state."""
        self.is_death_mode_active = False
        self.death_mode_reason = None
        logger.info("Death Mode manually reset by operator.")
        
    def evaluate_trade(
        self, 
        signal: TradingSignal, 
        current_equity: float, 
        current_positions_count: int, 
        current_exposure: float,
        current_drawdown: float = 0.0,
        current_loss_streak: int = 0
    ) -> RiskDecision:
        
        # 0. Latched Death Mode Check
        from app.config import config
        if getattr(config, "DEATH_MODE_ENABLED", False):
            dd_limit = getattr(config, "DEATH_MODE_DRAWDOWN_LIMIT", 0.10)
            streak_limit = getattr(config, "DEATH_MODE_LOSS_STREAK", 5)
            
            if current_drawdown >= dd_limit:
                self.is_death_mode_active = True
                self.death_mode_reason = f"Drawdown ({current_drawdown:.2%}) >= limit ({dd_limit:.2%})"
            elif current_loss_streak >= streak_limit:
                self.is_death_mode_active = True
                self.death_mode_reason = f"Loss streak ({current_loss_streak}) >= limit ({streak_limit})"

        if self.is_death_mode_active:
            from app.diagnostics.telemetry import telemetry
            from app.diagnostics.models import RejectionReason
            telemetry.record_rejection(RejectionReason.RISK_LIMIT)
            return RiskDecision(
                approved=False,
                requested_risk=0.0,
                allowed_risk=0.0,
                position_size=0.0,
                rejection_reason=f"Rejected: Death Mode Active ({self.death_mode_reason or 'Risk-Off Latch'})",
                relevant_limit="DEATH_MODE"
            )
            
        # 1. Portfolio Limits (Cooldown, Max Positions, Daily Loss, Exposure)
        limit_check, reason, limit_name = self.limits.can_open_new_position(
            current_positions_count, current_exposure, current_equity
        )
        from app.diagnostics.telemetry import telemetry
        from app.diagnostics.models import RejectionReason
        
        if not limit_check:
            # Try to map reason
            if limit_name == "DAILY_LOSS_LIMIT":
                reason_code = RejectionReason.DAILY_LOSS_LIMIT
            elif limit_name == "MAX_CONCURRENT_POSITIONS":
                reason_code = RejectionReason.POSITION_LIMIT
            elif limit_name == "COOLDOWN":
                reason_code = RejectionReason.LOSS_STREAK_COOLDOWN
            else:
                reason_code = RejectionReason.RISK_LIMIT
                
            telemetry.record_rejection(reason_code)
            return RiskDecision(
                approved=False,
                requested_risk=0.0,
                allowed_risk=0.0,
                position_size=0.0,
                rejection_reason=f"Rejected: {reason}",
                relevant_limit=limit_name
            )
            
        # 2. Need stop loss to size risk accurately
        if not signal.stop_loss or not signal.entry_price:
            telemetry.record_rejection(RejectionReason.MISSING_SL_OR_ENTRY)
            return RiskDecision(
                approved=False,
                requested_risk=0.0,
                allowed_risk=0.0,
                position_size=0.0,
                rejection_reason="Rejected: Stop loss and entry price required for position sizing.",
                relevant_limit="Missing Info"
            )
            
        requested_risk_amount = current_equity * self.risk_per_trade_pct
        
        # 3. Size Position
        position_size = calculate_position_size_by_stop_distance(
            risk_amount=requested_risk_amount,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )
        
        if position_size <= 0:
            return RiskDecision(
                approved=False,
                requested_risk=requested_risk_amount,
                allowed_risk=0.0,
                position_size=0.0,
                rejection_reason="Rejected: Calculated position size is zero or invalid.",
                relevant_limit="Position Size"
            )
            
        # 4. Max Position Value Limit
        position_value = position_size * signal.entry_price
        max_allowed_value = current_equity * self.max_position_value_pct
        
        if position_value > max_allowed_value:
            # Scale down position
            position_size = max_allowed_value / signal.entry_price
            allowed_risk = abs(signal.entry_price - signal.stop_loss) * position_size
            logger.info("Position scaled down to meet Max Position Value limit. Original Risk: %s, Allowed: %s", requested_risk_amount, allowed_risk)
        else:
            allowed_risk = requested_risk_amount
            
        return RiskDecision(
            approved=True,
            requested_risk=requested_risk_amount,
            allowed_risk=allowed_risk,
            position_size=position_size,
            rejection_reason=None,
            relevant_limit=None
        )

    def check_drawdown(
        self,
        drawdown_result,
    ) -> Tuple[bool, str]:
        """
        Deterministic drawdown veto check.

        Evaluates a DrawdownResult from DrawdownService against
        ``self.limits.max_drawdown_halt_pct``.

        Returns:
            (approved: bool, reason: str)
            - approved=True  -> drawdown within threshold; trading may proceed.
            - approved=False -> drawdown breach or invalid/missing data; VETO.

        Safety contract:
            Missing or INVALID_DATA inputs are treated as a REVIEW_REQUIRED
            veto — never silently safe.
            INSUFFICIENT_DATA (< 2 snapshots) is treated as monitoring-only
            (not a hard block) to allow trading during portfolio bootstrap.

        This method does NOT modify signals, weights, or position sizes.
        No automatic sizing changes are made.
        """
        from app.risk.drawdown import DrawdownStatus

        threshold = self.limits.max_drawdown_halt_pct

        if drawdown_result is None:
            return False, "DRAWDOWN_VETO: DrawdownResult is None — cannot assess risk. REVIEW_REQUIRED."

        status = drawdown_result.status

        if status == DrawdownStatus.INSUFFICIENT_DATA:
            # Bootstrap grace: fewer than 2 snapshots — allow trading, surface warning only.
            logger.info("Drawdown check: insufficient history — monitoring only, not blocking.")
            return True, "DRAWDOWN_INSUFFICIENT_DATA: fewer than 2 snapshots — monitoring only."

        if status == DrawdownStatus.INVALID_DATA:
            return False, (
                f"DRAWDOWN_VETO: invalid snapshot data "
                f"({drawdown_result.reason}). REVIEW_REQUIRED."
            )

        # status == OK — compare current drawdown against configured threshold
        current_dd = drawdown_result.current_drawdown_pct

        if current_dd >= threshold:
            return False, (
                f"DRAWDOWN_VETO: current drawdown {current_dd:.2f}% "
                f">= halt threshold {threshold:.2f}%. New positions blocked."
            )

        return True, (
            f"Drawdown OK: {current_dd:.2f}% < threshold {threshold:.2f}%."
        )
