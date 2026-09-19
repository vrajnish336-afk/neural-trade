from app.research.reproduction.models import ComparisonState, IndependentVerificationResult, ReproductionStatus
from app.research.governance.models import GovernanceState
from app.research.reproduction_intelligence.models import DiscrepancyImpactAssessment, ImpactLevel

class ImpactAnalyzer:
    
    @staticmethod
    def analyze(verification_result: IndependentVerificationResult) -> DiscrepancyImpactAssessment:
        comp_state = verification_result.comparison_state
        
        overall = ImpactLevel.NO_MATERIAL_IMPACT
        structural = ImpactLevel.NO_MATERIAL_IMPACT
        gov = GovernanceState.REPRODUCIBLE
        explanation = "No material impact."
        
        if comp_state == ComparisonState.STRUCTURAL_DIFFERENCE:
            overall = ImpactLevel.HIGH_IMPACT
            structural = ImpactLevel.CRITICAL_IMPACT
            gov = GovernanceState.REVALIDATION_REQUIRED
            explanation = "Structural drift detected (e.g. trade sequence mismatch). Research is fundamentally altered despite potential PnL similarity."
            
        elif comp_state == ComparisonState.MATERIAL_DIFFERENCE:
            overall = ImpactLevel.MODERATE_IMPACT
            structural = ImpactLevel.NO_MATERIAL_IMPACT
            gov = GovernanceState.REVALIDATION_REQUIRED
            explanation = "Material numerical drift detected."
            
        elif comp_state == ComparisonState.INCOMPATIBLE_OUTPUT:
            overall = ImpactLevel.CRITICAL_IMPACT
            structural = ImpactLevel.CRITICAL_IMPACT
            gov = GovernanceState.CONCLUSION_CONFLICT
            explanation = "Output structures are entirely incompatible."
            
        elif verification_result.status == ReproductionStatus.INSUFFICIENT_REPRODUCTION_DATA:
            overall = ImpactLevel.CRITICAL_IMPACT
            structural = ImpactLevel.NOT_ASSESSABLE
            gov = GovernanceState.INSUFFICIENT_AUDIT_TRAIL
            explanation = "Cannot reproduce due to missing data."

        return DiscrepancyImpactAssessment(
            overall_level=overall,
            structural_level=structural,
            governance_impact=gov,
            explanation=explanation,
            evidence=f"Derived deterministically from ComparisonState: {comp_state.value}"
        )
