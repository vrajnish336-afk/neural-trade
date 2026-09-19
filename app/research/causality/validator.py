from typing import List, Tuple
from app.research.evidence_graph.models import EvidenceNode
from app.research.causality.models import (
    MechanismCandidate, ConfoundingRisk, AlternativeExplanation, 
    CausalEvidenceLevel, CausalAssessmentState
)

class CausalValidator:
    def evaluate_mechanisms_and_alternatives(self, supporting_nodes: List[EvidenceNode], contradicting_nodes: List[EvidenceNode]) -> Tuple[List[MechanismCandidate], List[ConfoundingRisk], List[AlternativeExplanation]]:
        mechanisms = []
        confounders = []
        alternatives = []
        
        if not supporting_nodes:
            return mechanisms, confounders, alternatives
            
        # Detect Confounding Variables
        # If all supporting nodes share both a specific REGIME and a specific COST_SCENARIO, 
        # we can't tell which one causes the outcome.
        regimes = {n.metadata.get("regime") for n in supporting_nodes if "regime" in n.metadata}
        costs = {n.metadata.get("cost_scenario") for n in supporting_nodes if "cost_scenario" in n.metadata}
        
        if len(regimes) == 1 and len(costs) == 1:
            confounders.append(ConfoundingRisk(
                risk_id="conf_regime_cost",
                description="Multiple co-occurring conditions prevent isolated causal attribution.",
                overlapping_variables=["regime", "cost_scenario"]
            ))
            alternatives.append(AlternativeExplanation(
                explanation_id="alt_cost",
                description="The observed effect may be driven by transaction costs rather than the hypothesized mechanism.",
                supported_by_evidence=True
            ))
            
        # Create a deterministic MechanismCandidate
        # This represents the inferred mechanistic link. In observational studies, we extract this from metadata patterns.
        mech_desc = "Structured association identified between hypothesis conditions and performance."
        if len(regimes) == 1:
            mech_desc += f" Conditionally bounded to {list(regimes)[0]} regime."
            
        mechanisms.append(MechanismCandidate(
            mechanism_id="mech_1",
            description=mech_desc,
            supporting_evidence_count=len(supporting_nodes),
            contradicting_evidence_count=len(contradicting_nodes),
            falsified=(len(contradicting_nodes) > len(supporting_nodes))
        ))
        
        return mechanisms, confounders, alternatives

    def determine_level(self, has_temporal: bool, has_conditional: bool, indep_support: int, 
                       confounders: List[ConfoundingRisk], falsified: bool, 
                       has_consensus: bool, multiple_testing: bool) -> Tuple[CausalEvidenceLevel, CausalAssessmentState, List[str]]:
        gaps = []
        
        if falsified:
            return CausalEvidenceLevel.NO_RELATIONSHIP_EVIDENCE, CausalAssessmentState.CONFLICTED, gaps
            
        if not has_consensus:
            gaps.append("Need unseen-data replication to resolve direct contradiction.")
            return CausalEvidenceLevel.NO_RELATIONSHIP_EVIDENCE, CausalAssessmentState.UNRESOLVED, gaps
            
        if indep_support == 0:
            return CausalEvidenceLevel.NO_RELATIONSHIP_EVIDENCE, CausalAssessmentState.CAUSAL_EVIDENCE_INSUFFICIENT, gaps
            
        level = CausalEvidenceLevel.CORRELATIONAL
        
        if has_temporal:
            level = CausalEvidenceLevel.TEMPORAL_ASSOCIATION
            
        if has_conditional:
            level = CausalEvidenceLevel.CONDITIONAL_ASSOCIATION
            
        if indep_support >= 2 and not multiple_testing:
            level = CausalEvidenceLevel.REPEATED_STRUCTURAL_SUPPORT
            
        state = CausalAssessmentState.CAUSAL_IDENTIFICATION_LIMITED
        
        if confounders:
            gaps.append("Isolate co-occurring variables (e.g. compare identical methodology across different regimes/costs).")
            return level, state, gaps
            
        if multiple_testing:
            gaps.append("Obtain independent validation to rule out multiple-testing illusions.")
            return level, state, gaps
            
        if level == CausalEvidenceLevel.REPEATED_STRUCTURAL_SUPPORT:
            state = CausalAssessmentState.CAUSAL_EVIDENCE_MODERATE
        else:
            state = CausalAssessmentState.CAUSAL_EVIDENCE_WEAK
            
        # Limit to moderate unless a formal causal test (which observational research lacks) exists.
        return level, state, gaps
