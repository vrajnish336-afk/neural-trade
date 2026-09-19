from typing import List, Optional
from datetime import datetime
from app.research.revalidation.models import (
    RevalidationAssessment, RevalidationAssessmentState, EvidenceDirection
)
from app.research.reproduction.models import ComparisonState
from app.research.discrepancy_isolation.models import IsolationAttributionState

class EvidenceConsolidator:
    
    @staticmethod
    def evaluate_evidence(
        base_assessment: RevalidationAssessment,
        reproduction_comparison_state: Optional[ComparisonState],
        isolation_attributions: List[IsolationAttributionState],
        evidence_as_of: datetime
    ) -> RevalidationAssessment:
        
        # Future Data Guard
        if evidence_as_of > base_assessment.as_of:
            raise ValueError("FUTURE_INFORMATION_VIOLATION: Cannot use future evidence for historical assessment.")

        base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_NOT_ASSESSABLE
        base_assessment.evidence_direction = EvidenceDirection.INSUFFICIENT
        
        if not reproduction_comparison_state:
            return base_assessment
            
        if reproduction_comparison_state in [ComparisonState.EXACT_MATCH, ComparisonState.WITHIN_TOLERANCE]:
            base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_CONFIRMS_ORIGINAL
            base_assessment.evidence_direction = EvidenceDirection.SUPPORTING
            base_assessment.explanation = "Reproduction perfectly matched or fell within bounded numerical tolerance."
            return base_assessment
            
        if reproduction_comparison_state == ComparisonState.INCOMPATIBLE_OUTPUT:
            base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_CONFLICTS_WITH_ORIGINAL
            base_assessment.evidence_direction = EvidenceDirection.CONTRADICTING
            base_assessment.explanation = "Reproduction completely incompatible with historical evidence."
            return base_assessment
            
        # We have a discrepancy. Let's look at isolation evidence.
        if not isolation_attributions:
            # We know it differs but we haven't isolated why.
            base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_INCONCLUSIVE
            base_assessment.evidence_direction = EvidenceDirection.NEUTRAL
            base_assessment.explanation = "Material or structural drift detected, but causal attribution is pending."
            return base_assessment
            
        if IsolationAttributionState.ISOLATION_SUPPORTED in isolation_attributions:
            base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL
            base_assessment.evidence_direction = EvidenceDirection.CONTRADICTING
            base_assessment.explanation = "Controlled OFAT isolation confirms structural sensitivity."
        elif IsolationAttributionState.PARTIAL_ISOLATION in isolation_attributions:
            base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL
            base_assessment.evidence_direction = EvidenceDirection.CONTRADICTING
            base_assessment.explanation = "Controlled OFAT explains some numerical drift, but structural differences remain."
        elif IsolationAttributionState.INTERACTION_UNRESOLVED in isolation_attributions:
            base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_INCONCLUSIVE
            base_assessment.evidence_direction = EvidenceDirection.NEUTRAL
            base_assessment.explanation = "Discrepancy involves unresolved multi-factor interactions."
        else:
            base_assessment.assessment_state = RevalidationAssessmentState.REVALIDATION_INCONCLUSIVE
            base_assessment.evidence_direction = EvidenceDirection.INSUFFICIENT
            base_assessment.explanation = "Isolation plans executed but failed to resolve the discrepancy."
            
        return base_assessment
