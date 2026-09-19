import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Set
import logging
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.models import NodeType, EdgeRelationship, EvidenceNode
from app.research.synthesis.models import ResearchHypothesis
from app.research.hypothesis_validation.models import (
    HypothesisValidationResult, ValidationState, EvidenceClassification, FalsificationState
)
from app.research.hypothesis_validation.repository import ValidationRepository
from app.research.hypothesis_validation.falsification import FalsificationEngine

logger = logging.getLogger(__name__)

class HypothesisValidator:
    def __init__(self, max_depth: int = 5, max_nodes: int = 200):
        self.repo = ValidationRepository()
        self.graph_repo = EvidenceGraphRepository()
        self.falsification_engine = FalsificationEngine()
        self.max_depth = max_depth
        self.max_nodes = max_nodes

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def _check_eligibility(self, h: ResearchHypothesis, as_of: datetime) -> tuple[bool, str]:
        if not h.hypothesis_id: return False, "Missing hypothesis_id"
        if not h.hypothesis_text: return False, "Missing hypothesis_text"
        if h.status.value in ["NOT_TESTABLE", "REJECTED", "SUPERSEDED"]: return False, f"Hypothesis status is {h.status.value}"
        if not h.falsification_condition: return False, "Missing falsification_condition"
        if not h.expected_observation: return False, "Missing expected_observation"
        # as_of boundary check: if hypothesis was generated after the validation boundary, it can't be validated.
        h_as_of = h.as_of.replace(tzinfo=timezone.utc) if h.as_of.tzinfo is None else h.as_of
        if h_as_of > as_of:
            return False, "Hypothesis generated after as_of boundary"
        return True, "Eligible"

    def validate(self, hypothesis: ResearchHypothesis, as_of: Optional[datetime] = None) -> HypothesisValidationResult:
        """Evaluates evidence for a given hypothesis within strict as_of bounds."""
        if not as_of:
            as_of = datetime.now(timezone.utc)
        as_of = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        is_eligible, reason = self._check_eligibility(hypothesis, as_of)
        if not is_eligible:
            return HypothesisValidationResult(
                validation_id=self._deterministic_hash(f"val_fail_{hypothesis.hypothesis_id}_{as_of.timestamp()}"),
                hypothesis_id=hypothesis.hypothesis_id,
                research_identity=hypothesis.research_identity,
                status=ValidationState.NOT_ELIGIBLE_FOR_VALIDATION,
                validation_state=ValidationState.NOT_ELIGIBLE_FOR_VALIDATION,
                explanation=f"Not eligible: {reason}",
                as_of=as_of,
                created_at=datetime.now(timezone.utc)
            )

        # We collect evidence starting from the hypothesis's research_identity
        all_nodes = self.graph_repo.get_nodes(as_of=as_of)
        target_nodes = [n for n in all_nodes if n.identity_hash == hypothesis.research_identity]
        
        supporting_nodes: List[EvidenceNode] = []
        contradicting_nodes: List[EvidenceNode] = []
        visited = set()
        edges_used = set()
        
        if target_nodes:
            focal_node = target_nodes[0]
            self._traverse_evidence(focal_node.node_id, supporting_nodes, contradicting_nodes, visited, edges_used, as_of, 0)
        
        support_count = len(supporting_nodes)
        conflict_count = len(contradicting_nodes)
        
        falsification_state, falsification_reason = self.falsification_engine.evaluate(hypothesis.falsification_condition, contradicting_nodes)
        
        evidence_state = EvidenceClassification.INSUFFICIENT
        validation_state = ValidationState.INCONCLUSIVE
        explanation = ""
        
        if falsification_state == FalsificationState.TRIGGERED:
            evidence_state = EvidenceClassification.CONTRADICTING
            validation_state = ValidationState.REJECTED
            explanation = f"REJECTED: {falsification_reason}"
        else:
            if support_count > 3 and conflict_count == 0:
                evidence_state = EvidenceClassification.SUPPORTING
                validation_state = ValidationState.SUPPORTED
                explanation = f"SUPPORTED: Strong supporting evidence ({support_count} nodes) and no contradictions."
            elif support_count > 0 and conflict_count == 0:
                evidence_state = EvidenceClassification.SUPPORTING
                validation_state = ValidationState.INCONCLUSIVE
                explanation = f"INCONCLUSIVE: Some supporting evidence ({support_count} nodes), but insufficient for full support."
            elif support_count > 0 and conflict_count > 0:
                if support_count > conflict_count:
                    evidence_state = EvidenceClassification.NEUTRAL
                    validation_state = ValidationState.WEAKENED
                    explanation = f"WEAKENED: Evidence exists but is conflicted ({support_count} support, {conflict_count} contradict)."
                else:
                    evidence_state = EvidenceClassification.CONTRADICTING
                    validation_state = ValidationState.CONFLICTED
                    explanation = f"CONFLICTED: Contradicting evidence outweighs support ({support_count} support, {conflict_count} contradict)."
            else:
                evidence_state = EvidenceClassification.INSUFFICIENT
                validation_state = ValidationState.INSUFFICIENT_EVIDENCE
                explanation = "INSUFFICIENT_EVIDENCE: No applicable evidence found."
        
        vid = self._deterministic_hash(f"val_{hypothesis.hypothesis_id}_{support_count}_{conflict_count}_{falsification_state.value}_{as_of.timestamp()}")
        
        result = HypothesisValidationResult(
            validation_id=vid,
            hypothesis_id=hypothesis.hypothesis_id,
            research_identity=hypothesis.research_identity,
            status=validation_state,
            validation_state=validation_state,
            evidence_state=evidence_state,
            support_score=float(support_count),
            contradiction_score=float(conflict_count),
            evidence_count=support_count + conflict_count,
            supporting_evidence_ids=[n.node_id for n in supporting_nodes],
            contradicting_evidence_ids=[n.node_id for n in contradicting_nodes],
            falsification_triggered=falsification_state,
            falsification_reason=falsification_reason,
            explanation=explanation,
            as_of=as_of,
            created_at=datetime.now(timezone.utc)
        )
        
        self.repo.save_validation(result)
        return result

    def _traverse_evidence(self, node_id: str, support: List[EvidenceNode], contradict: List[EvidenceNode], visited: Set[str], edges_used: Set[str], as_of: datetime, depth: int):
        if depth >= self.max_depth or len(visited) >= self.max_nodes:
            return
        if node_id in visited:
            return
        visited.add(node_id)
        
        node = self.graph_repo.get_node(node_id)
        if not node: return
        n_as_of = node.as_of.replace(tzinfo=timezone.utc) if node.as_of.tzinfo is None else node.as_of
        if n_as_of > as_of:
            return
            
        edges = self.graph_repo.get_edges_for_node(node_id, as_of=as_of, direction='in')
        for e in edges:
            if e.edge_id in edges_used: continue
            edges_used.add(e.edge_id)
            
            src = self.graph_repo.get_node(e.source_node_id)
            if not src: continue
            src_as_of = src.as_of.replace(tzinfo=timezone.utc) if src.as_of.tzinfo is None else src.as_of
            if src_as_of > as_of:
                continue
                
            if e.relationship_type in [EdgeRelationship.SUPPORTS, EdgeRelationship.STRENGTHENS, EdgeRelationship.VALIDATES]:
                if src not in support:
                    support.append(src)
            elif e.relationship_type in [EdgeRelationship.CONTRADICTS, EdgeRelationship.WEAKENS, EdgeRelationship.INVALIDATES]:
                if src not in contradict:
                    contradict.append(src)
                    
            self._traverse_evidence(e.source_node_id, support, contradict, visited, edges_used, as_of, depth + 1)
