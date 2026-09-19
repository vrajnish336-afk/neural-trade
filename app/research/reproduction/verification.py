from app.research.reproduction.models import (
    OriginalResearchOutput, 
    ReproducedResearchOutput, 
    IndependentVerificationResult, 
    ReproductionStatus, 
    ReproductionConfidence, 
    ComparisonState
)
from app.research.reproduction.comparison import ResearchComparator

class VerificationEngine:
    
    @staticmethod
    def verify(manifest_id: str, orig: OriginalResearchOutput, repo: ReproducedResearchOutput) -> IndependentVerificationResult:
        comp_state, discrepancies = ResearchComparator.compare(orig, repo)
        
        status = ReproductionStatus.NOT_COMPARABLE
        confidence = ReproductionConfidence.LOW_REPRODUCIBILITY_CONFIDENCE
        explanation = "Discrepancy detected."
        
        if comp_state == ComparisonState.EXACT_MATCH:
            status = ReproductionStatus.REPRODUCED_EXACTLY
            confidence = ReproductionConfidence.HIGH_REPRODUCIBILITY_CONFIDENCE
            explanation = "Reproduced output matched historical output perfectly."
        elif comp_state == ComparisonState.WITHIN_TOLERANCE:
            status = ReproductionStatus.REPRODUCED_WITHIN_TOLERANCE
            confidence = ReproductionConfidence.HIGH_REPRODUCIBILITY_CONFIDENCE
            explanation = "Reproduced output matched within deterministic bounds."
        elif comp_state == ComparisonState.STRUCTURAL_DIFFERENCE:
            status = ReproductionStatus.REPRODUCTION_MATCHED_STRUCTURALLY
            confidence = ReproductionConfidence.MODERATE_REPRODUCIBILITY_CONFIDENCE
            explanation = "Structural divergence occurred (trade count or sequence altered)."
        elif comp_state == ComparisonState.MATERIAL_DIFFERENCE:
            status = ReproductionStatus.REPRODUCTION_DIFFERED
            confidence = ReproductionConfidence.LOW_REPRODUCIBILITY_CONFIDENCE
            explanation = "Material numerical difference outside of acceptable tolerances."
            
        reval_required = (status in [
            ReproductionStatus.REPRODUCTION_DIFFERED, 
            ReproductionStatus.REPRODUCTION_FAILED, 
            ReproductionStatus.INSUFFICIENT_REPRODUCTION_DATA
        ])
        
        return IndependentVerificationResult(
            manifest_id=manifest_id,
            reproduction_id=repo.reproduction_id,
            status=status,
            confidence=confidence,
            comparison_state=comp_state,
            discrepancies=discrepancies,
            independent_replication_supported=False, # Reproduction is NEVER replication
            revalidation_required=reval_required,
            explanation=explanation
        )
