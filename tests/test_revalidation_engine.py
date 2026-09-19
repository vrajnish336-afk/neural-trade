import pytest
from datetime import datetime, timezone
from app.research.revalidation.models import (
    RevalidationAssessment, RevalidationAssessmentState, EvidenceDirection
)
from app.research.revalidation.assessment import EvidenceConsolidator
from app.research.revalidation.consolidation_service import EvidenceConsolidationService
from app.research.reproduction.models import ComparisonState, IndependentVerificationResult
from app.research.discrepancy_isolation.models import IsolationAttributionState, IsolationComparison
from app.research.reproduction_intelligence.models import ImpactLevel
from app.research.governance.models import ResearchConclusionRevision, GovernanceState
from app.research.replication.models import EvidenceStrengthLevel
from app.research.revalidation.models import DecayState

def test_evidence_consolidation_confirms_original():
    base = RevalidationAssessment(
        assessment_id="a1", hypothesis_id="h1", validation_id="v1", research_identity="id1",
        as_of=datetime(2023, 1, 1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
    )
    
    result = EvidenceConsolidator.evaluate_evidence(
        base, ComparisonState.EXACT_MATCH, [], datetime(2023, 1, 1, tzinfo=timezone.utc)
    )
    
    assert result.assessment_state == RevalidationAssessmentState.REVALIDATION_CONFIRMS_ORIGINAL
    assert result.evidence_direction == EvidenceDirection.SUPPORTING

def test_evidence_consolidation_weakens_original():
    base = RevalidationAssessment(
        assessment_id="a1", hypothesis_id="h1", validation_id="v1", research_identity="id1",
        as_of=datetime(2023, 1, 1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
    )
    
    result = EvidenceConsolidator.evaluate_evidence(
        base, ComparisonState.STRUCTURAL_DIFFERENCE, [IsolationAttributionState.ISOLATION_SUPPORTED], datetime(2023, 1, 1, tzinfo=timezone.utc)
    )
    
    assert result.assessment_state == RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL
    assert result.evidence_direction == EvidenceDirection.CONTRADICTING

def test_evidence_consolidation_inconclusive():
    base = RevalidationAssessment(
        assessment_id="a1", hypothesis_id="h1", validation_id="v1", research_identity="id1",
        as_of=datetime(2023, 1, 1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
    )
    
    result = EvidenceConsolidator.evaluate_evidence(
        base, ComparisonState.STRUCTURAL_DIFFERENCE, [IsolationAttributionState.INTERACTION_UNRESOLVED], datetime(2023, 1, 1, tzinfo=timezone.utc)
    )
    
    assert result.assessment_state == RevalidationAssessmentState.REVALIDATION_INCONCLUSIVE
    assert result.evidence_direction == EvidenceDirection.NEUTRAL

def test_future_data_rejection():
    base = RevalidationAssessment(
        assessment_id="a1", hypothesis_id="h1", validation_id="v1", research_identity="id1",
        as_of=datetime(2023, 1, 1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
    )
    
    with pytest.raises(ValueError, match="FUTURE_INFORMATION_VIOLATION"):
        EvidenceConsolidator.evaluate_evidence(
            base, ComparisonState.EXACT_MATCH, [], datetime(2023, 1, 2, tzinfo=timezone.utc)
        )

def test_consolidation_service():
    service = EvidenceConsolidationService()
    base = RevalidationAssessment(
        assessment_id="a1", hypothesis_id="h1", validation_id="v1", research_identity="id1",
        as_of=datetime(2023, 1, 1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
    )
    
    v_res = IndependentVerificationResult(
        verification_id="v2",
        reproduction_id="r2",
        specification_id="s1",
        manifest_id="m1",
        original_fingerprint="f1",
        reproduced_fingerprint="f2",
        comparison_state=ComparisonState.STRUCTURAL_DIFFERENCE,
        verified_match=False,
        status="REPRODUCTION_DIFFERED",
        confidence="HIGH_REPRODUCIBILITY_CONFIDENCE",
        explanation="Test"
    )
    
    iso_comp = IsolationComparison(
        experiment_id="e1",
        baseline_output_fingerprint="b1",
        experiment_output_fingerprint="e2",
        numerical_impact=ImpactLevel.MODERATE_IMPACT,
        structural_impact=ImpactLevel.CRITICAL_IMPACT,
        attribution=IsolationAttributionState.ISOLATION_SUPPORTED,
        explanation="test"
    )
    
    result = service.consolidate_and_assess(
        base, "conc_1", v_res, [iso_comp], datetime(2023, 1, 1, tzinfo=timezone.utc)
    )
    
    assert result.assessment_state == RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL
    assert result.methodology_version == "revalidation_v2"
    assert "r2" in result.discrepancy_analysis_ids
    assert "e1" in result.isolation_plan_ids
