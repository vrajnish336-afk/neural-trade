from typing import List
from app.research.revalidation.models import DecayState, RevalidationReason
from app.research.replication.models import EvidenceStrengthLevel
from app.research.hypothesis_validation.models import HypothesisValidationResult

class RevalidationEvaluator:
    def evaluate_strength_modification(self, original_strength: EvidenceStrengthLevel, decay_state: DecayState, reasons: List[RevalidationReason], validation: HypothesisValidationResult, new_contradictions: int) -> tuple[EvidenceStrengthLevel, bool]:
        """
        Conditionally degrades the Phase 35 EvidenceStrengthLevel based on new drift, decay, and contradictions.
        Returns (new_strength, revalidation_required).
        """
        # If falsification was triggered natively, we must respect it
        if validation.falsification_triggered == "TRIGGERED":
            return EvidenceStrengthLevel.CONFLICTED, False
            
        strength = original_strength
        required = False
        
        # 1. Decay impacts
        if decay_state == DecayState.STALE:
            if strength in [EvidenceStrengthLevel.STRONG, EvidenceStrengthLevel.MODERATE]:
                strength = EvidenceStrengthLevel.STALE
            required = True
            
        # 2. Contradiction impacts
        if new_contradictions > 0:
            if strength == EvidenceStrengthLevel.STRONG:
                strength = EvidenceStrengthLevel.MODERATE
            elif strength == EvidenceStrengthLevel.MODERATE:
                strength = EvidenceStrengthLevel.WEAK
            elif strength == EvidenceStrengthLevel.WEAK:
                strength = EvidenceStrengthLevel.CONFLICTED
            required = True
            
        # 3. Drift impacts
        if RevalidationReason.METHODOLOGY_CHANGED in reasons or RevalidationReason.NEW_REGIME in reasons:
            if strength in [EvidenceStrengthLevel.STRONG, EvidenceStrengthLevel.MODERATE]:
                strength = EvidenceStrengthLevel.FRAGILE
            required = True
            
        # 4. Phase 35 inheritances
        if RevalidationReason.INSUFFICIENT_INDEPENDENT_REPLICATION in reasons or RevalidationReason.MULTIPLE_TESTING_RISK in reasons:
            if strength in [EvidenceStrengthLevel.STRONG, EvidenceStrengthLevel.MODERATE]:
                strength = EvidenceStrengthLevel.FRAGILE
            required = True
            
        if RevalidationReason.INSUFFICIENT_SAMPLE in reasons:
            strength = EvidenceStrengthLevel.INSUFFICIENT
            required = True
            
        # Only preserve strong if absolutely nothing went wrong
        if original_strength == EvidenceStrengthLevel.STRONG and strength == EvidenceStrengthLevel.STRONG:
            required = False
            
        return strength, required
