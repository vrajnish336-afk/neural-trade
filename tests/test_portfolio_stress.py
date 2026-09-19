import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from app.research.portfolio_intelligence.models import (
    PortfolioResearchSnapshot, DiversificationAssessment, PortfolioResearchAssessment
)
from app.research.portfolio_stress.models import (
    PortfolioStressScenario, PortfolioStressScenarioType, 
    PortfolioFailureAssessment, StressSeverity, PortfolioResilienceAssessment
)
from app.research.portfolio_stress.scenarios import ScenarioPerturbator
from app.research.portfolio_stress.evaluator import PortfolioStressEvaluator

def _mock_baseline():
    return PortfolioResearchSnapshot(
        portfolio_id="port_1",
        candidate_ids=["A", "B"],
        dataset_identity="test",
        common_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        common_end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        weights={"A": 0.5, "B": 0.5},
        cost_model={},
        risk_model={},
        as_of=datetime(2024, 6, 1, tzinfo=timezone.utc),
        correlation_matrix={},
        diversification_state=DiversificationAssessment.MODERATE_DIVERSIFICATION_EVIDENCE,
        research_assessment=PortfolioResearchAssessment.ROBUST_PORTFOLIO_EVIDENCE
    )

def test_baseline_immutability():
    returns = {"A": pd.Series(np.ones(100)), "B": pd.Series(np.ones(100))}
    baseline = _mock_baseline()
    scenario = PortfolioStressScenario(
        portfolio_id="port_1",
        scenario_type=PortfolioStressScenarioType.COST_SHOCK,
        scenario_parameters={"multiplier": 2.0},
        dataset_identity="test",
        time_boundary_start=baseline.common_start,
        time_boundary_end=baseline.common_end,
        cost_model={},
        risk_model={},
        as_of=datetime(2024, 7, 1, tzinfo=timezone.utc),
        is_synthetic=True
    )
    
    # Run evaluator
    PortfolioStressEvaluator.evaluate_scenario(baseline, scenario, returns, {})
    
    # Assert weights didn't change
    assert baseline.weights["A"] == 0.5
    # Assert return object not mutated
    assert returns["A"].iloc[0] == 1.0

def test_cost_shock_logic():
    returns = {"A": pd.Series([0.01, 0.0, -0.01])}
    stressed = ScenarioPerturbator.apply_cost_shock(returns, multiplier=2.0)
    
    # friction = 0.0005 * 2 = 0.001
    # 0.01 - 0.001 = 0.009
    assert stressed["A"].iloc[0] == pytest.approx(0.009)
    # 0.0 -> remains 0.0
    assert stressed["A"].iloc[1] == 0.0
    # -0.01 - 0.001 = -0.011
    assert stressed["A"].iloc[2] == pytest.approx(-0.011)

def test_missing_candidate_shock():
    weights = {"A": 0.5, "B": 0.5}
    stressed = ScenarioPerturbator.apply_missing_candidate(weights, "A")
    assert stressed["A"] == 0.0
    assert stressed["B"] == 0.5 # NO silent normalization!

def test_evaluator_strict_as_of():
    returns = {"A": pd.Series(np.ones(100)), "B": pd.Series(np.ones(100))}
    baseline = _mock_baseline()
    
    # Scenario is strictly EARLIER than baseline
    scenario = PortfolioStressScenario(
        portfolio_id="port_1",
        scenario_type=PortfolioStressScenarioType.COST_SHOCK,
        scenario_parameters={},
        dataset_identity="test",
        time_boundary_start=baseline.common_start,
        time_boundary_end=baseline.common_end,
        cost_model={},
        risk_model={},
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        is_synthetic=True
    )
    
    with pytest.raises(ValueError, match="cannot be earlier than baseline"):
        PortfolioStressEvaluator.evaluate_scenario(baseline, scenario, returns, {})
