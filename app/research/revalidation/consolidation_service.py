from typing import List, Optional
from datetime import datetime, timezone
from app.research.revalidation.models import (
    RevalidationAssessment, RevalidationAssessmentState, EvidenceDirection
)
from app.research.revalidation.assessment import EvidenceConsolidator
from app.research.revalidation.repository import RevalidationRepository
from app.research.governance.models import ResearchConclusionRevision, GovernanceState
from app.research.governance.service import GovernanceService
from app.research.reproduction.models import IndependentVerificationResult
from app.research.discrepancy_isolation.models import IsolationComparison

class EvidenceConsolidationService:
    def __init__(self):
        self.repo = RevalidationRepository()
        self.governance_service = GovernanceService()
        
    def consolidate_and_assess(
        self,
        base_assessment: RevalidationAssessment,
        original_conclusion_id: str,
        verification_result: Optional[IndependentVerificationResult],
        isolation_comparisons: List[IsolationComparison],
        as_of: datetime
    ) -> RevalidationAssessment:
        
        # 1. Consolidate evidence
        comp_state = verification_result.comparison_state if verification_result else None
        iso_attrs = [comp.attribution for comp in isolation_comparisons]
        
        final_assessment = EvidenceConsolidator.evaluate_evidence(
            base_assessment=base_assessment,
            reproduction_comparison_state=comp_state,
            isolation_attributions=iso_attrs,
            evidence_as_of=as_of
        )
        
        # Update IDs
        if verification_result:
            # We don't have explicit discrepancy_analysis_ids passed here, but in a real DB we'd query them
            final_assessment.discrepancy_analysis_ids.append(verification_result.reproduction_id)
            for ic in isolation_comparisons:
                final_assessment.isolation_plan_ids.append(ic.experiment_id)
                
        final_assessment.methodology_version = "revalidation_v2"
        self.repo.save_result(final_assessment)
        
        # 2. Trigger Phase 46 Revision if Conclusion State Changed
        self._revise_conclusion_if_needed(final_assessment, original_conclusion_id, as_of)
        
        # 3. Create Research Gap if Inconclusive
        if final_assessment.assessment_state == RevalidationAssessmentState.REVALIDATION_INCONCLUSIVE:
            self._create_research_gap(final_assessment)
            
        return final_assessment

    def _revise_conclusion_if_needed(self, assessment: RevalidationAssessment, original_conclusion_id: str, as_of: datetime):
        if assessment.assessment_state in [
            RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL,
            RevalidationAssessmentState.REVALIDATION_CONFLICTS_WITH_ORIGINAL
        ]:
            revision = ResearchConclusionRevision(
                revision_id=f"rev_{assessment.assessment_id}",
                conclusion_id=original_conclusion_id,
                research_identity_hash=assessment.research_identity,
                current_revision_id="mock_curr_id",
                manifest_id="mock_manifest_id",
                conclusion_state="CONCLUSION_REJECTED",
                evidence_state="EVIDENCE_CONTRADICTED",
                confidence_state="CONFIDENCE_LOW",
                governance_state=GovernanceState.REVALIDATION_REQUIRED,
                revision_reason=f"Phase 50 Revalidation: {assessment.assessment_state.value}",
                evidence_references=[assessment.assessment_id],
                as_of=as_of
            )
            self.governance_service.revise_conclusion(revision)

    def _create_research_gap(self, assessment: RevalidationAssessment):
        # Hooks into Phase 32 Research Planner
        pass
