from typing import List, Optional
from datetime import datetime
from app.research.knowledge_intelligence.models import ResearchKnowledgeClaim, KnowledgeState
from app.research.evidence_graph.models import EvidenceEdge, EdgeRelationship
from app.research.reasoning.models import (
    ConclusionType, ReasoningStrength, ReasoningUncertainty, ResearchReasoningResult
)
import hashlib

class ReasoningRuleBase:
    rule_id: str = "UNKNOWN"
    
    def _hash(self, *args) -> str:
        s = "_".join(str(a) for a in args)
        return hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]
        
    def evaluate(self, claims: List[ResearchKnowledgeClaim], edges: List[EvidenceEdge], as_of: datetime) -> Optional[ResearchReasoningResult]:
        raise NotImplementedError

class Rule001_IndependentSupport(ReasoningRuleBase):
    rule_id = "RULE_001_INDEPENDENT_SUPPORT"
    
    def evaluate(self, claims: List[ResearchKnowledgeClaim], edges: List[EvidenceEdge], as_of: datetime) -> Optional[ResearchReasoningResult]:
        # Are there 2+ supported claims sharing the same condition?
        supported = [c for c in claims if c.knowledge_state == KnowledgeState.ESTABLISHED_WITHIN_BOUNDARY]
        if len(supported) >= 2:
            return ResearchReasoningResult(
                reasoning_id=self._hash(self.rule_id, [c.claim_id for c in supported], as_of.isoformat()),
                rule_id=self.rule_id,
                conclusion_type=ConclusionType.CONDITIONAL_INFERENCE,
                canonical_statement="Multiple independent claims support inference conditionally upon explicit boundaries.",
                source_claim_ids=[c.claim_id for c in supported],
                reasoning_strength=ReasoningStrength.STRONG,
                uncertainty_state=ReasoningUncertainty.CONDITIONAL_UNCERTAINTY,
                explanation_trace=f"Found {len(supported)} ESTABLISHED_WITHIN_BOUNDARY claims. Evaluated via {self.rule_id}.",
                as_of=as_of,
                created_at=as_of
            )
        return None

class Rule003_ConflictedEvidence(ReasoningRuleBase):
    rule_id = "RULE_003_CONFLICTED_EVIDENCE"
    
    def evaluate(self, claims: List[ResearchKnowledgeClaim], edges: List[EvidenceEdge], as_of: datetime) -> Optional[ResearchReasoningResult]:
        # Any CONTRADICTS edges?
        contradictions = [e for e in edges if e.relationship_type == EdgeRelationship.CONTRADICTS]
        if contradictions:
            involved = set()
            for e in contradictions:
                involved.add(e.source_node_id)
                involved.add(e.target_node_id)
            
            return ResearchReasoningResult(
                reasoning_id=self._hash(self.rule_id, list(involved), as_of.isoformat()),
                rule_id=self.rule_id,
                conclusion_type=ConclusionType.CONFLICTED_INFERENCE,
                canonical_statement="Structural contradictions identified between evidence nodes.",
                source_relationship_ids=[e.edge_id for e in contradictions],
                source_claim_ids=list(involved),
                reasoning_strength=ReasoningStrength.CONFLICTED,
                uncertainty_state=ReasoningUncertainty.CONFLICTED,
                explanation_trace=f"Found {len(contradictions)} CONTRADICTS edges. Evaluated via {self.rule_id}.",
                as_of=as_of,
                created_at=as_of
            )
        return None

class Rule004_RevalidationRequired(ReasoningRuleBase):
    rule_id = "RULE_004_REVALIDATION_REQUIRED"
    
    def evaluate(self, claims: List[ResearchKnowledgeClaim], edges: List[EvidenceEdge], as_of: datetime) -> Optional[ResearchReasoningResult]:
        weakened = [c for c in claims if c.knowledge_state == KnowledgeState.WEAKENED]
        if weakened:
            return ResearchReasoningResult(
                reasoning_id=self._hash(self.rule_id, [c.claim_id for c in weakened], as_of.isoformat()),
                rule_id=self.rule_id,
                conclusion_type=ConclusionType.REQUIRES_REVALIDATION,
                canonical_statement="Prior claims have been weakened by Phase 50 revalidation.",
                source_claim_ids=[c.claim_id for c in weakened],
                reasoning_strength=ReasoningStrength.WEAK,
                uncertainty_state=ReasoningUncertainty.HIGH_UNCERTAINTY,
                explanation_trace=f"Found {len(weakened)} WEAKENED claims. Revalidation loop required. Evaluated via {self.rule_id}.",
                as_of=as_of,
                created_at=as_of
            )
        return None

class Rule005_InteractionTestRequired(ReasoningRuleBase):
    rule_id = "RULE_005_INTERACTION_TEST_REQUIRED"
    
    def evaluate(self, claims: List[ResearchKnowledgeClaim], edges: List[EvidenceEdge], as_of: datetime) -> Optional[ResearchReasoningResult]:
        # Exposes gaps?
        exposes = [e for e in edges if e.relationship_type == EdgeRelationship.EXPOSES_GAP]
        if exposes:
            return ResearchReasoningResult(
                reasoning_id=self._hash(self.rule_id, [e.edge_id for e in exposes], as_of.isoformat()),
                rule_id=self.rule_id,
                conclusion_type=ConclusionType.REQUIRES_INTERACTION_TEST,
                canonical_statement="Graph explicitly EXPOSES_GAP. Interaction tests bounded by Phase 49 needed.",
                source_relationship_ids=[e.edge_id for e in exposes],
                reasoning_strength=ReasoningStrength.INSUFFICIENT,
                uncertainty_state=ReasoningUncertainty.SCOPE_LIMITED,
                explanation_trace=f"Found {len(exposes)} EXPOSES_GAP edges. Evaluated via {self.rule_id}.",
                as_of=as_of,
                created_at=as_of
            )
        return None

RULES = [
    Rule001_IndependentSupport(),
    Rule003_ConflictedEvidence(),
    Rule004_RevalidationRequired(),
    Rule005_InteractionTestRequired()
]
