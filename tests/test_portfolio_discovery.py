import pytest
from datetime import datetime, timezone

from app.research.portfolio_stress.models import (
    PortfolioStressResult, PortfolioFailureAssessment, StressSeverity, PortfolioResilienceAssessment, PortfolioStressScenarioType
)
from app.research.portfolio_discovery.models import PortfolioResearchQuestionState, NoveltyState
from app.research.portfolio_discovery.discovery import PortfolioDiscoveryEngine
from app.research.portfolio_discovery.signals import PortfolioSignalExtractor

def _mock_stress_result(failure: PortfolioFailureAssessment, severity: StressSeverity, as_of: datetime) -> PortfolioStressResult:
    return PortfolioStressResult(
        portfolio_id="port_1",
        scenario_id="scen_1",
        scenario_type=PortfolioStressScenarioType.COST_SHOCK,
        baseline_reference_id="port_1",
        stress_assessment=failure,
        severity=severity,
        resilience=PortfolioResilienceAssessment.FRAGILE,
        affected_candidates=["A"],
        drawdown_metrics={},
        correlation_metrics={},
        cost_metrics={},
        sample_size=100,
        limitations=[],
        as_of=as_of
    )

def test_failure_signal_extraction():
    assert PortfolioSignalExtractor.extract_gap(PortfolioFailureAssessment.CORRELATED_FAILURE) == "CORRELATED_FAILURE_GAP"
    assert PortfolioSignalExtractor.extract_gap(PortfolioFailureAssessment.COST_FRAGILITY) == "COST_RESILIENCE_GAP"

def test_discovery_engine_novelty():
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    res = _mock_stress_result(PortfolioFailureAssessment.CORRELATED_FAILURE, StressSeverity.HIGH, as_of)
    
    q1 = PortfolioDiscoveryEngine.evaluate(res, [])
    assert q1.novelty == NoveltyState.NOVEL
    assert q1.status == PortfolioResearchQuestionState.REVIEW_REQUIRED
    
    # Run again with q1 in existing
    q2 = PortfolioDiscoveryEngine.evaluate(res, [q1])
    assert q2.novelty == NoveltyState.DUPLICATE
    assert q2.status == PortfolioResearchQuestionState.DUPLICATE

def test_already_resolved_saturation():
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    res = _mock_stress_result(PortfolioFailureAssessment.CORRELATED_FAILURE, StressSeverity.HIGH, as_of)
    
    q1 = PortfolioDiscoveryEngine.evaluate(res, [])
    q1.status = PortfolioResearchQuestionState.COMPLETED
    
    q2 = PortfolioDiscoveryEngine.evaluate(res, [q1])
    assert q2.novelty == NoveltyState.ALREADY_RESOLVED
    assert q2.status == PortfolioResearchQuestionState.ALREADY_RESOLVED

def test_no_gap_rejection():
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    res = _mock_stress_result(PortfolioFailureAssessment.NO_MATERIAL_FAILURE_DETECTED, StressSeverity.LOW, as_of)
    
    q1 = PortfolioDiscoveryEngine.evaluate(res, [])
    assert q1.status == PortfolioResearchQuestionState.REJECTED
    assert q1.priority == 0.0

def test_priority_not_allocation():
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    res = _mock_stress_result(PortfolioFailureAssessment.CORRELATED_FAILURE, StressSeverity.CRITICAL, as_of)
    
    q1 = PortfolioDiscoveryEngine.evaluate(res, [])
    # Critical failure gets high priority to RESEARCH, not to trade
    assert q1.priority > 0.5 
    assert q1.priority_breakdown.uncertainty_weight == 1.0
