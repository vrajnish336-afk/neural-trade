import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.models import EdgeRelationship, EvidenceNode, NodeType
from app.research.hypothesis_validation.models import HypothesisValidationResult, FalsificationState
from app.research.replication.models import ResearchReplicationResult
from app.research.revalidation.models import RevalidationAssessment, RevalidationReason, DecayState
from app.research.revalidation.repository import RevalidationRepository
from app.research.revalidation.decay import DecayEngine
from app.research.revalidation.drift import DriftEngine
from app.research.revalidation.revalidation import RevalidationEvaluator

logger = logging.getLogger(__name__)

class RevalidationService:
    def __init__(self):
        self.repo = RevalidationRepository()
        self.graph_repo = EvidenceGraphRepository()
        self.decay_engine = DecayEngine()
        self.drift_engine = DriftEngine()
        self.evaluator = RevalidationEvaluator()

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def evaluate(self, validation: HypothesisValidationResult, replication: Optional[ResearchReplicationResult] = None, as_of: Optional[datetime] = None) -> RevalidationAssessment:
        if not as_of:
            as_of = datetime.now(timezone.utc)
        as_of = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # Validation bounding check
        val_as_of = validation.as_of.replace(tzinfo=timezone.utc) if validation.as_of.tzinfo is None else validation.as_of
        if val_as_of > as_of:
            raise ValueError("Historical assessment cannot use future validation results.")

        # Gather base experiments
        base_experiments = []
        for nid in validation.supporting_evidence_ids:
            node = self.graph_repo.get_node(nid)
            if node and (node.as_of.replace(tzinfo=timezone.utc) if node.as_of.tzinfo is None else node.as_of) <= as_of:
                base_experiments.append(node)

        # 1. Decay 
        age_days, decay_state = self.decay_engine.calculate_decay(base_experiments, as_of)

        # Gather ALL experiments on the graph connected to this research identity *after* the validation
        # Find the focal node for the hypothesis identity
        focal_nodes = [n for n in self.graph_repo.get_nodes() if n.identity_hash == validation.research_identity and n.node_type in [NodeType.RESEARCH_QUESTION, NodeType.HYPOTHESIS]]
        
        newer_experiments = []
        new_contradictions_count = 0
        all_reasons = set()
        
        if focal_nodes:
            focal_id = focal_nodes[0].node_id
            edges = self.graph_repo.get_edges_for_node(focal_id, as_of=as_of, direction='in')
            for e in edges:
                src = self.graph_repo.get_node(e.source_node_id)
                if not src: continue
                src_as_of = src.as_of.replace(tzinfo=timezone.utc) if src.as_of.tzinfo is None else src.as_of
                if src_as_of > as_of: continue
                
                # If this node was created AFTER the validation was run, it's new evidence.
                if src_as_of > val_as_of and src.node_type == NodeType.EXPERIMENT:
                    newer_experiments.append(src)
                    if e.relationship_type in [EdgeRelationship.CONTRADICTS, EdgeRelationship.WEAKENS, EdgeRelationship.INVALIDATES]:
                        new_contradictions_count += 1
                        all_reasons.add(RevalidationReason.NEW_CONTRADICTION)

        # 2. Drift
        drift_flags, drift_reasons = self.drift_engine.detect_drift(validation, newer_experiments, base_experiments)
        all_reasons.update(drift_reasons)
        
        # 3. Incorporate Phase 35 Replication risks
        original_strength = replication.evidence_strength if replication else validation.evidence_state
        if replication:
            if replication.replication.multiple_testing_risk:
                all_reasons.add(RevalidationReason.MULTIPLE_TESTING_RISK)
            if replication.replication.total_independent_units == 0 and replication.replication.same_dataset_units < 2:
                all_reasons.add(RevalidationReason.INSUFFICIENT_INDEPENDENT_REPLICATION)
            if replication.insufficient_sample_flag:
                all_reasons.add(RevalidationReason.INSUFFICIENT_SAMPLE)
                
        if decay_state == DecayState.STALE:
            all_reasons.add(RevalidationReason.EVIDENCE_TOO_OLD)
            
        if validation.falsification_triggered == FalsificationState.TRIGGERED:
            all_reasons.add(RevalidationReason.FALSIFICATION_WARNING)

        # 4. Strength modification
        new_strength, req = self.evaluator.evaluate_strength_modification(
            original_strength, decay_state, list(all_reasons), validation, new_contradictions_count
        )

        assessment_id = self._deterministic_hash(f"reval_{validation.validation_id}_{as_of.timestamp()}")
        
        explanation = f"Decay State: {decay_state.value}. Age: {round(age_days,1) if age_days else 'Unknown'} days. "
        if new_contradictions_count > 0:
            explanation += f"Found {new_contradictions_count} new contradicting experiments. "
        if drift_flags:
            explanation += f"Drift detected: {', '.join(drift_flags)}. "
            
        res = RevalidationAssessment(
            assessment_id=assessment_id,
            hypothesis_id=validation.hypothesis_id,
            validation_id=validation.validation_id,
            replication_assessment_id=replication.assessment_id if replication else None,
            research_identity=validation.research_identity,
            evidence_age_days=age_days,
            decay_state=decay_state,
            drift_flags=drift_flags,
            revalidation_reasons=list(all_reasons),
            original_evidence_strength=original_strength,
            current_evidence_strength=new_strength,
            explanation=explanation,
            revalidation_required=req,
            methodology_version="revalidation_v1",
            as_of=as_of,
            created_at=datetime.now(timezone.utc)
        )
        self.repo.save_result(res)
        
        # Publish gap to Phase 32 Planner if required (mock step representing planner integration)
        if req:
            self._publish_research_gap(res)
            
        return res

    def _publish_research_gap(self, res: RevalidationAssessment):
        # Hooks into Phase 32 Research Planner without auto-executing experiments.
        pass
