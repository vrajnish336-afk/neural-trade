import logging
from typing import Dict, List, Optional, Any
from app.config import config

logger = logging.getLogger(__name__)

class PerformanceWeightingEngine:
    """
    Engine for calculating adaptive strategy weight multipliers based on 
    rolling paper-trade performance metrics.
    """
    
    def __init__(
        self,
        min_sample_size: int = 10,
        alpha: float = 0.1,
        min_weight: float = 0.5,
        max_weight: float = 2.0
    ):
        self.min_sample_size = min_sample_size
        self.alpha = alpha
        self.min_weight = min_weight
        self.max_weight = max_weight
        self._current_weights: Dict[str, float] = {}

    def calculate_weight(
        self,
        strategy_name: str,
        trades: List[Dict[str, Any]],
        previous_weight: Optional[float] = None
    ) -> float:
        """
        Calculates the adaptive weight multiplier for a strategy.
        If STRATEGY_WEIGHTING_ENABLED is False or trades < min_sample_size, returns 1.0.
        Applies EMA smoothing and clamps output to [min_weight, max_weight].
        """
        if not getattr(config, "STRATEGY_WEIGHTING_ENABLED", False):
            return 1.0

        if not trades or len(trades) < self.min_sample_size:
            return 1.0

        # Calculate raw performance score based on win rate and net return ratio
        wins = sum(1 for t in trades if t.get("realized_pnl", 0.0) > 0)
        win_rate = wins / len(trades)
        
        total_pnl = sum(t.get("realized_pnl", 0.0) for t in trades)
        pnl_factor = 1.0 + max(-0.5, min(0.5, total_pnl / 1000.0))
        
        # Raw performance multiplier: baseline 1.0 + (win_rate - 0.5) * 2.0 * pnl_factor
        raw_multiplier = 1.0 + (win_rate - 0.5) * 2.0 * pnl_factor

        # Previous weight resolution
        prev = previous_weight if previous_weight is not None else self._current_weights.get(strategy_name, 1.0)

        # EMA smoothing: new_weight = (alpha * raw) + ((1 - alpha) * prev)
        smoothed = (self.alpha * raw_multiplier) + ((1.0 - self.alpha) * prev)

        # Clamp strictly between [min_weight, max_weight]
        clamped = max(self.min_weight, min(self.max_weight, smoothed))
        self._current_weights[strategy_name] = clamped

        return clamped
