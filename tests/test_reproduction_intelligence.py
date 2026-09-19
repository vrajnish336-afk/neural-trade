import pytest
from datetime import datetime
from app.research.reproduction.models import (
    IndependentVerificationResult, ComparisonState, ReproductionStatus, ReproductionConfidence,
    ReproductionDiscrepancy, DiscrepancyCategory
)
from app.research.governance.change_detection import ChangeCategory
from app.research.reproduction_intelligence.attribution import AttributionEngine
from app.research.reproduction_intelligence.models import RootCauseCategory, RootCauseConfidence
from app.research.reproduction_intelligence.service import DiscrepancyIntelligenceService

def test_attribution_no_changes():
    # If there are discrepancies but NO input changes, it must flag NONDETERMINISM.
    causes = AttributionEngine.attribute([ChangeCategory.NO_MATERIAL_CHANGE], [DiscrepancyCategory.NUMERICAL_DRIFT])
    assert len(causes) == 1
    assert causes[0].cause == RootCauseCategory.STRUCTURAL_NONDETERMINISM
    assert causes[0].confidence == RootCauseConfidence.POSSIBLE

def test_attribution_single_change():
    # Single change isolates causation cleanly
    causes = AttributionEngine.attribute([ChangeCategory.DATA_CHANGED], [DiscrepancyCategory.NUMERICAL_DRIFT])
    assert len(causes) == 1
    assert causes[0].cause == RootCauseCategory.DATASET_CHANGED
    assert causes[0].confidence == RootCauseConfidence.CONFIRMED

def test_attribution_multiple_changes_prevent_overclaim():
    # If Data AND Code changed, neither can be individually CONFIRMED.
    causes = AttributionEngine.attribute([ChangeCategory.DATA_CHANGED, ChangeCategory.CODE_CHANGED], [DiscrepancyCategory.NUMERICAL_DRIFT])
    assert len(causes) == 3
    assert any(c.cause == RootCauseCategory.MULTIPLE_CONTRIBUTING_FACTORS for c in causes)
    
    # The specific components are only POSSIBLE, never CONFIRMED
    data_cause = next(c for c in causes if c.cause == RootCauseCategory.DATASET_CHANGED)
    assert data_cause.confidence == RootCauseConfidence.POSSIBLE

def test_intelligence_service():
    ver = IndependentVerificationResult(
        manifest_id="m1", reproduction_id="r1",
        status=ReproductionStatus.REPRODUCTION_DIFFERED,
        confidence=ReproductionConfidence.LOW_REPRODUCIBILITY_CONFIDENCE,
        comparison_state=ComparisonState.MATERIAL_DIFFERENCE,
        explanation="Differs",
        discrepancies=[ReproductionDiscrepancy(category=DiscrepancyCategory.NUMERICAL_DRIFT, description="", evidence_context="")]
    )
    
    analysis = DiscrepancyIntelligenceService.analyze_discrepancy(ver, [ChangeCategory.METHODOLOGY_CHANGED])
    
    assert analysis.status == "ANALYZED"
    assert analysis.impact.overall_level == "MODERATE_IMPACT"
    assert analysis.research_priority == "CRITICAL_REVALIDATION"
    assert len(analysis.root_causes) == 1
    assert analysis.root_causes[0].cause == RootCauseCategory.METHODOLOGY_CHANGED
    assert analysis.root_causes[0].confidence == RootCauseConfidence.CONFIRMED
