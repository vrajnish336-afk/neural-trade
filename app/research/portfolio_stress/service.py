import pandas as pd
from typing import Dict, List
from datetime import datetime
from app.research.portfolio_intelligence.models import PortfolioResearchSnapshot
from app.research.portfolio_stress.models import PortfolioStressScenario, PortfolioStressResult
from app.research.portfolio_stress.evaluator import PortfolioStressEvaluator

class PortfolioStressService:
    
    def evaluate_adversarial_scenario(
        self,
        baseline_snapshot: PortfolioResearchSnapshot,
        scenario: PortfolioStressScenario,
        returns_map: Dict[str, pd.Series],
        drawdowns_map: Dict[str, pd.Series]
    ) -> PortfolioStressResult:
        """
        Orchestrates an adversarial research scenario against a declared baseline.
        Ensures baseline immutability.
        """
        return PortfolioStressEvaluator.evaluate_scenario(
            baseline_snapshot=baseline_snapshot,
            scenario=scenario,
            returns_map=returns_map,
            drawdowns_map=drawdowns_map
        )
