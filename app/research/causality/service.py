import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.models import NodeType
from app.research.hypothesis_validation.models import HypothesisValidationResult, FalsificationState
from app.research.replication.models import ResearchReplicationResult
from app.research.revalidation.models import RevalidationAssessment
from app.research.consensus.models import ConsensusAssessment, ConsensusState

from app.research.causality.models import CausalAssessment, CausalEvidenceLevel, CausalAssessmentState
from app.research.causality.repository import CausalRepository
from app.research.causality.validator import CausalValidator

logger = logging.getLogger(__name__)

class CausalService:
    def __init__(self):
        self.repo = CausalRepository()
        self.graph_repo = EvidenceGraphRepository()
        self.validator = CausalValidator()

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def evaluate(self, hypothesis_id: str, identity_hash: str, validation: HypothesisValidationResult, consensus: ConsensusAssessment, replication: Optional[ResearchReplicationResult] = None, revalidation: Optional[RevalidationAssessment] = None, as_of: Optional[datetime] = None) -> CausalAssessment:
        if not as_of:
            as_of = datetime.now(timezone.utc)
        as_of = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # Historical lock check
        val_as_of = validation.as_of.replace(tzinfo=timezone.utc) if validation.as_of.tzinfo is None else validation.as_of
        if val_as_of > as_of:
            raise ValueError("Historical assessment cannot use future validation results.")
            
        # 1. Gather nodes based on consensus state
        supp_nodes = []
        con_nodes = []
        for nid in validation.supporting_evidence_ids:
            n = self.graph_repo.get_node(nid)
            if n and (n.as_of.replace(tzinfo=timezone.utc) if n.as_of.tzinfo is None else n.as_of) <= as_of:
                supp_nodes.append(n)
                
        # To get contradictions, we look at the edges on the graph directed at the focal node
        focal_nodes = [n for n in self.graph_repo.get_nodes() if n.identity_hash == identity_hash and n.node_type in [NodeType.RESEARCH_QUESTION, NodeType.HYPOTHESIS]]
        if focal_nodes:
            edges = self.graph_repo.get_edges_for_node(focal_nodes[0].node_id, as_of=as_of, direction='in')
            for e in edges:
                if e.relationship_type.name in ["CONTRADICTS", "WEAKENS"]:
                    n = self.graph_repo.get_node(e.source_node_id)
                    if n and (n.as_of.replace(tzinfo=timezone.utc) if n.as_of.tzinfo is None else n.as_of) <= as_of:
                        con_nodes.append(n)
        
        # 2. Check Temporal Ordering
        # Very basic check: did the condition exist before the validation was authored?
        # A true temporal check would look at `observed_at` vs outcome timestamp.
        temporal_verified = False
        if supp_nodes:
            first_obs = min((n.observed_at for n in supp_nodes if n.observed_at), default=None)
            if first_obs and (first_obs.replace(tzinfo=timezone.utc) if first_obs.tzinfo is None else first_obs) < val_as_of:
                temporal_verified = True
                
        # 3. Analyze Mechanisms and Confounders
        mechanisms, confounders, alternatives = self.validator.evaluate_mechanisms_and_alternatives(supp_nodes, con_nodes)
        
        # 4. Synthesize Level
        has_conditional = len(consensus.conditional_conditions) > 0
        falsified = (validation.falsification_triggered == FalsificationState.TRIGGERED) or consensus.falsification_triggered
        has_consensus = consensus.state in [ConsensusState.CONSENSUS_SUPPORTED, ConsensusState.CONDITIONAL_CONSENSUS, ConsensusState.PARTIAL_CONSENSUS]
        multiple_testing = consensus.multiple_testing_risk
        
        level, state, gaps = self.validator.determine_level(
            has_temporal=temporal_verified,
            has_conditional=has_conditional,
            indep_support=consensus.independent_support_count,
            confounders=confounders,
            falsified=falsified,
            has_consensus=has_consensus,
            multiple_testing=multiple_testing
        )
        
        explanation = f"Evaluated causal evidence. Confounders found: {len(confounders)}. Level mapped to {level.value}."
        
        res = CausalAssessment(
            assessment_id=self._deterministic_hash(f"cau_{hypothesis_id}_{as_of.timestamp()}"),
            hypothesis_id=hypothesis_id, research_identity=identity_hash,
            causal_level=level, assessment_state=state,
            mechanisms=mechanisms, confounders=confounders, alternatives=alternatives,
            temporal_ordering_verified=temporal_verified,
            conditional_constraints=consensus.conditional_conditions,
            explanation=explanation, research_gaps=gaps,
            as_of=as_of, created_at=datetime.now(timezone.utc)
        )
        self.repo.save_result(res)
        return res
