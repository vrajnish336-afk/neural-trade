from app.research.reproduction.models import ComparisonState
from app.research.reproduction_intelligence.models import ImpactLevel
from app.research.discrepancy_isolation.models import IsolationComparison, IsolationAttributionState

class IsolationComparator:
    
    @staticmethod
    def compare(
        experiment_id: str,
        baseline_fingerprint: str,
        experiment_fingerprint: str,
        comparison_state: ComparisonState
    ) -> IsolationComparison:
        
        num = ImpactLevel.NO_MATERIAL_IMPACT
        struct = ImpactLevel.NO_MATERIAL_IMPACT
        attr = IsolationAttributionState.PENDING
        explanation = "Compared against baseline."
        
        if comparison_state == ComparisonState.STRUCTURAL_DIFFERENCE:
            num = ImpactLevel.MODERATE_IMPACT
            struct = ImpactLevel.CRITICAL_IMPACT
            attr = IsolationAttributionState.ISOLATION_SUPPORTED
            explanation = "Structural drift successfully isolated to this factor."
        elif comparison_state == ComparisonState.MATERIAL_DIFFERENCE:
            num = ImpactLevel.MODERATE_IMPACT
            struct = ImpactLevel.NO_MATERIAL_IMPACT
            attr = IsolationAttributionState.PARTIAL_ISOLATION
            explanation = "Numerical drift isolated, but does not explain structural differences."
        elif comparison_state == ComparisonState.EXACT_MATCH or comparison_state == ComparisonState.WITHIN_TOLERANCE:
            attr = IsolationAttributionState.ISOLATION_UNRESOLVED
            explanation = "Output matches baseline. Factor does not explain the discrepancy."
            
        return IsolationComparison(
            experiment_id=experiment_id,
            baseline_output_fingerprint=baseline_fingerprint,
            experiment_output_fingerprint=experiment_fingerprint,
            numerical_impact=num,
            structural_impact=struct,
            attribution=attr,
            explanation=explanation
        )
