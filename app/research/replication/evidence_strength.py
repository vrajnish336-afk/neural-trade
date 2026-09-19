from typing import List
from app.research.evidence_graph.models import EvidenceNode
from app.research.replication.models import GeneralizationState, EvidenceStrengthLevel, ReplicationAssessment
from app.research.hypothesis_validation.models import HypothesisValidationResult, ValidationState, FalsificationState

class EvidenceStrengthAnalyzer:

    def analyze_generalization(self, supporting_nodes: List[EvidenceNode]) -> GeneralizationState:
        # Measure diversity in regimes and dataset names
        regimes = set()
        datasets = set()
        for exp in [n for n in supporting_nodes if n.node_type == "EXPERIMENT"]:
            if "regime" in exp.metadata:
                regimes.add(exp.metadata["regime"])
            if "dataset_id" in exp.metadata:
                datasets.add(exp.metadata["dataset_id"])
                
        if len(regimes) > 1 and len(datasets) > 1:
            return GeneralizationState.GENERALIZES
        elif len(regimes) > 1 or len(datasets) > 1:
            return GeneralizationState.PARTIAL_GENERALIZATION
        elif len(supporting_nodes) > 0:
            return GeneralizationState.LIMITED_SCOPE
            
        return GeneralizationState.INSUFFICIENT_EVIDENCE

    def assess_strength(self, val_result: HypothesisValidationResult, rep_assessment: ReplicationAssessment, gen_state: GeneralizationState) -> tuple[EvidenceStrengthLevel, str, bool]:
        """
        Determines evidence strength heuristically based on independent evidence counts, 
        falsification triggers, contradictions, and data breadth.
        """
        
        # Falsification overriding
        if val_result.falsification_triggered == FalsificationState.TRIGGERED:
            return EvidenceStrengthLevel.CONFLICTED, "Falsification triggered or constraints disrespected. Evidence is fatally conflicted.", False
            
        # Sample size enforcement based on Phase 28/34 heuristics
        insufficient_sample = False
        if val_result.evidence_count == 0 or rep_assessment.evidence_nodes_assessed == 0:
            return EvidenceStrengthLevel.INSUFFICIENT, "No valid evidence available at this boundary.", True
            
        # Look for low trade count alerts in metadata if possible, but we can also use independent units as a proxy
        if rep_assessment.total_independent_units == 0 and rep_assessment.same_dataset_units < 2:
            insufficient_sample = True
            
        if val_result.validation_state == ValidationState.CONFLICTED:
            return EvidenceStrengthLevel.CONFLICTED, f"Evidence is conflicted ({val_result.contradiction_score} contradictions).", insufficient_sample
            
        if val_result.validation_state == ValidationState.WEAKENED:
            return EvidenceStrengthLevel.WEAK, "Evidence is weakened by contradictions.", insufficient_sample
            
        if rep_assessment.multiple_testing_risk:
            return EvidenceStrengthLevel.FRAGILE, "Multiple testing risk detected. High repetition on same data.", insufficient_sample

        if rep_assessment.total_independent_units >= 2 and gen_state == GeneralizationState.GENERALIZES:
            return EvidenceStrengthLevel.STRONG, f"Strong independent replication ({rep_assessment.total_independent_units} independent sources) with broad generalization.", insufficient_sample
            
        if rep_assessment.total_independent_units >= 1 and gen_state in [GeneralizationState.PARTIAL_GENERALIZATION, GeneralizationState.GENERALIZES]:
            return EvidenceStrengthLevel.MODERATE, "Moderate independent replication and partial generalization.", insufficient_sample
            
        if rep_assessment.same_dataset_units >= 2:
            return EvidenceStrengthLevel.FRAGILE, "Fragile evidence. Repeated heavily on overlapping/same datasets without independent confirmation.", insufficient_sample
            
        return EvidenceStrengthLevel.WEAK, "Weak evidence base. Needs further independent validation.", insufficient_sample
