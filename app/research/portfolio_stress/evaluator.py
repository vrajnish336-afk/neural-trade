import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timezone
import numpy as np

from app.research.portfolio_intelligence.evaluator import PortfolioEvaluator
from app.research.portfolio_intelligence.portfolio import PortfolioComposer
from app.research.portfolio_intelligence.models import PortfolioResearchSnapshot

from app.research.portfolio_stress.models import (
    PortfolioStressScenario, PortfolioStressResult, 
    PortfolioFailureAssessment, StressSeverity, PortfolioResilienceAssessment,
    PortfolioStressScenarioType
)
from app.research.portfolio_stress.scenarios import ScenarioPerturbator

class PortfolioStressEvaluator:
    
    @staticmethod
    def evaluate_scenario(
        baseline_snapshot: PortfolioResearchSnapshot,
        scenario: PortfolioStressScenario,
        returns_map: Dict[str, pd.Series],
        drawdowns_map: Dict[str, pd.Series]
    ) -> PortfolioStressResult:
        
        # We must NOT modify baseline references directly.
        stress_returns_map = {k: v.copy() for k, v in returns_map.items()}
        stress_drawdowns_map = {k: v.copy() for k, v in drawdowns_map.items()}
        stress_weights = dict(baseline_snapshot.weights)
        
        # Ensure 'as_of' boundaries are respected chronologically
        if scenario.as_of < baseline_snapshot.as_of:
             raise ValueError("Stress scenario 'as_of' cannot be earlier than baseline 'as_of'.")

        failure_assessment = PortfolioFailureAssessment.NO_MATERIAL_FAILURE_DETECTED
        severity = StressSeverity.LOW
        resilience = PortfolioResilienceAssessment.ROBUST_UNDER_TESTED_SCENARIOS
        affected_candidates = []

        try:
            # Apply perturbations
            if scenario.scenario_type == PortfolioStressScenarioType.COST_SHOCK:
                multiplier = scenario.scenario_parameters.get("multiplier", 2.0)
                stress_returns_map = ScenarioPerturbator.apply_cost_shock(stress_returns_map, multiplier)
                
            elif scenario.scenario_type == PortfolioStressScenarioType.MISSING_CANDIDATE:
                drop_id = scenario.scenario_parameters.get("drop_candidate")
                if drop_id:
                    stress_weights = ScenarioPerturbator.apply_missing_candidate(stress_weights, drop_id)
                    affected_candidates.append(drop_id)
            
            elif scenario.scenario_type == PortfolioStressScenarioType.DATA_GAP:
                stress_returns_map = ScenarioPerturbator.apply_data_integrity_stress(stress_returns_map)

            # Construct perturbed portfolio
            # Use inner PortfolioComposer but expect it to potentially throw on bad integrity data
            try:
                # We skip validate_weights because missing candidate sets weight to 0 and sum != 1.0 (cash drag)
                # But we still evaluate the math.
                aligned_returns = PortfolioComposer.align_series(stress_returns_map)
                if aligned_returns.empty:
                    raise ValueError("No valid data post-stress.")
                
                # If Data_Gap injected NaNs, the alignment forward fills. We check if variance blew up.
                port_return = PortfolioComposer.construct_portfolio_returns(aligned_returns, stress_weights)
                
                # Check for NaNs surviving which means data integrity failed
                if port_return.isna().sum() > 0:
                    failure_assessment = PortfolioFailureAssessment.DATA_INTEGRITY_FAILURE
                    severity = StressSeverity.CRITICAL
                    resilience = PortfolioResilienceAssessment.HIGHLY_FRAGILE
                
                # Evaluate outcome diffs
                port_cumulative = (1 + port_return).cumprod() - 1
                if port_cumulative.iloc[-1] < -0.2:  # Arbitrary failure threshold for research simulation
                    severity = StressSeverity.HIGH
                    resilience = PortfolioResilienceAssessment.FRAGILE
                    
                    if scenario.scenario_type == PortfolioStressScenarioType.COST_SHOCK:
                        failure_assessment = PortfolioFailureAssessment.COST_FRAGILITY
                    elif scenario.scenario_type == PortfolioStressScenarioType.MISSING_CANDIDATE:
                        failure_assessment = PortfolioFailureAssessment.SINGLE_CANDIDATE_DEPENDENCY
                
            except Exception as e:
                 # Complete mathematical break
                 failure_assessment = PortfolioFailureAssessment.DATA_INTEGRITY_FAILURE
                 severity = StressSeverity.CRITICAL
                 resilience = PortfolioResilienceAssessment.HIGHLY_FRAGILE
                 
        except Exception as e:
            # Catchall for unhandled
            failure_assessment = PortfolioFailureAssessment.MULTIPLE_FAILURE_MODES
            severity = StressSeverity.CRITICAL
            resilience = PortfolioResilienceAssessment.HIGHLY_FRAGILE
            
        sample_size = len(list(stress_returns_map.values())[0]) if stress_returns_map else 0
        if sample_size < 30:
            severity = StressSeverity.INSUFFICIENT_EVIDENCE
            resilience = PortfolioResilienceAssessment.INSUFFICIENT_EVIDENCE
            failure_assessment = PortfolioFailureAssessment.INSUFFICIENT_EVIDENCE

        return PortfolioStressResult(
            portfolio_id=baseline_snapshot.portfolio_id,
            scenario_id=scenario.scenario_id,
            scenario_type=scenario.scenario_type,
            baseline_reference_id=baseline_snapshot.portfolio_id,
            stress_assessment=failure_assessment,
            severity=severity,
            resilience=resilience,
            affected_candidates=affected_candidates,
            drawdown_metrics={},
            correlation_metrics={},
            cost_metrics={},
            sample_size=sample_size,
            limitations=["Stress assumptions are not market facts", "No profitability guarantee"],
            as_of=scenario.as_of
        )
