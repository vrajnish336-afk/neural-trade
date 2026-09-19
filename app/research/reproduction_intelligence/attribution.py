from typing import List, Dict
from app.research.governance.change_detection import ChangeCategory
from app.research.reproduction.models import DiscrepancyCategory
from app.research.reproduction_intelligence.models import (
    RootCauseAttribution, RootCauseCategory, RootCauseConfidence
)

class AttributionEngine:
    
    @staticmethod
    def map_change_to_cause(change: ChangeCategory) -> RootCauseCategory:
        mapping = {
            ChangeCategory.DATA_CHANGED: RootCauseCategory.DATASET_CHANGED,
            ChangeCategory.PARAMETERS_CHANGED: RootCauseCategory.CONFIGURATION_CHANGED,
            ChangeCategory.STRATEGY_CHANGED: RootCauseCategory.CONFIGURATION_CHANGED,
            ChangeCategory.METHODOLOGY_CHANGED: RootCauseCategory.METHODOLOGY_CHANGED,
            ChangeCategory.CODE_CHANGED: RootCauseCategory.CODE_CHANGED,
            ChangeCategory.DEPENDENCIES_CHANGED: RootCauseCategory.DEPENDENCY_CHANGED,
            ChangeCategory.SCHEMA_CHANGED: RootCauseCategory.SCHEMA_CHANGED,
            ChangeCategory.AS_OF_CHANGED: RootCauseCategory.AS_OF_CHANGED,
            ChangeCategory.SEED_CHANGED: RootCauseCategory.SEED_CHANGED,
            ChangeCategory.NO_MATERIAL_CHANGE: RootCauseCategory.NO_ROOT_CAUSE
        }
        return mapping.get(change, RootCauseCategory.UNRESOLVED_DISCREPANCY)

    @staticmethod
    def attribute(changes: List[ChangeCategory], discrepancies: List[DiscrepancyCategory]) -> List[RootCauseAttribution]:
        if not discrepancies:
            return [RootCauseAttribution(
                cause=RootCauseCategory.NO_ROOT_CAUSE,
                confidence=RootCauseConfidence.CONFIRMED,
                evidence="No discrepancies detected in Phase 47 reproduction.",
                isolation_status="Fully Isolated",
                explanation="Outputs matched exactly or within floating point drift."
            )]

        # Filter out NO_MATERIAL_CHANGE from the causal list
        active_changes = [c for c in changes if c != ChangeCategory.NO_MATERIAL_CHANGE]

        if not active_changes:
            return [RootCauseAttribution(
                cause=RootCauseCategory.STRUCTURAL_NONDETERMINISM,
                confidence=RootCauseConfidence.POSSIBLE,
                evidence="Output discrepancies exist despite NO material input changes.",
                isolation_status="Not Isolated",
                explanation="Discrepancy detected with identical inputs. Likely nondeterminism.",
                limitations=["Cannot definitively prove nondeterminism without repeated variance testing."]
            )]

        # Single active change + Discrepancy = CONFIRMED
        if len(active_changes) == 1:
            cause = AttributionEngine.map_change_to_cause(active_changes[0])
            return [RootCauseAttribution(
                cause=cause,
                confidence=RootCauseConfidence.CONFIRMED,
                evidence=f"Input change detected: {active_changes[0].value}",
                isolation_status="Isolated",
                explanation=f"A single material input difference ({active_changes[0].value}) directly explains the output discrepancy."
            )]
            
        # Multiple active changes + Discrepancy = POSSIBLE (Causal overclaim protection)
        causes = [RootCauseAttribution(
            cause=RootCauseCategory.MULTIPLE_CONTRIBUTING_FACTORS,
            confidence=RootCauseConfidence.CONFIRMED,
            evidence=f"Multiple input changes detected: {[c.value for c in active_changes]}",
            isolation_status="Not Isolated",
            explanation="Multiple factors changed. Available evidence cannot isolate their individual causal contributions.",
            limitations=["One-factor-at-a-time control runs required to isolate true root cause."]
        )]
        
        for c in active_changes:
            rc = AttributionEngine.map_change_to_cause(c)
            causes.append(RootCauseAttribution(
                cause=rc,
                confidence=RootCauseConfidence.POSSIBLE,
                evidence=f"Input change detected: {c.value}",
                isolation_status="Confounded",
                explanation="This factor changed but causal impact cannot be isolated from other changes."
            ))
            
        return causes
