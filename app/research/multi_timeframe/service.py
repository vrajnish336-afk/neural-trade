import logging
from typing import List, Callable, Optional
from datetime import datetime, timezone
from app.core.models import MarketBar
from app.backtesting.models import CostConfig
from app.research.multi_timeframe.models import TimeframeHierarchy, TimeframeAblationResult
from app.research.multi_timeframe.evaluator import MultiTimeframeEvaluator

logger = logging.getLogger(__name__)

class MultiTimeframeService:
    """Orchestrates multi-timeframe backtesting and ablation experiments."""
    
    def __init__(self):
        # We don't have a formal repository created in the prompt for Phase 41 beyond simple SQLite conventions,
        # but the prompt dictates minimal state persistence.
        pass

    def evaluate_ablation(self, candidate_id: str, hierarchy: TimeframeHierarchy, bars: List[MarketBar],
                          htf_logic: Callable, mtf_logic: Callable, ltf_logic: Callable, 
                          cost_config: CostConfig, as_of: datetime) -> TimeframeAblationResult:
                              
        evaluator = MultiTimeframeEvaluator(cost_config)
        return evaluator.run_ablation(candidate_id, hierarchy, bars, htf_logic, mtf_logic, ltf_logic, as_of)
