import pandas as pd
from typing import Dict, List
from datetime import datetime
from app.research.portfolio_intelligence.models import PortfolioResearchSnapshot
from app.research.portfolio_intelligence.evaluator import PortfolioEvaluator

class PortfolioIntelligenceService:
    
    def evaluate_portfolio_candidates(
        self,
        candidate_ids: List[str],
        weights: Dict[str, float],
        dataset_identity: str,
        returns_map: Dict[str, pd.Series],
        drawdowns_map: Dict[str, pd.Series],
        cost_model: dict,
        risk_model: dict,
        as_of: datetime
    ) -> PortfolioResearchSnapshot:
        """
        Orchestrates portfolio-level correlation and diversification assessment.
        Ensures NO SURVIVORSHIP BIAS by enforcing the as_of boundary.
        """
        return PortfolioEvaluator.evaluate(
            candidate_ids=candidate_ids,
            weights=weights,
            dataset_identity=dataset_identity,
            returns_map=returns_map,
            drawdowns_map=drawdowns_map,
            cost_model=cost_model,
            risk_model=risk_model,
            as_of=as_of
        )
