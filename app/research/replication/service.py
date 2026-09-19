import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.hypothesis_validation.models import HypothesisValidationResult
from app.research.replication.models import ResearchReplicationResult
from app.research.replication.repository import ReplicationRepository
from app.research.replication.replication import ReplicationAnalyzer
from app.research.replication.evidence_strength import EvidenceStrengthAnalyzer

logger = logging.getLogger(__name__)

class ReplicationService:
    def __init__(self):
        self.repo = ReplicationRepository()
        self.graph_repo = EvidenceGraphRepository()
        self.rep_analyzer = ReplicationAnalyzer()
        self.strength_analyzer = EvidenceStrengthAnalyzer()

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def evaluate(self, validation: HypothesisValidationResult, as_of: Optional[datetime] = None) -> ResearchReplicationResult:
        if not as_of:
            as_of = datetime.now(timezone.utc)
        as_of = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # We only consider evidence that existed at or before as_of
        if (validation.as_of.replace(tzinfo=timezone.utc) if validation.as_of.tzinfo is None else validation.as_of) > as_of:
            raise ValueError("Validation result is from the future relative to the requested as_of bound.")

        supporting_nodes = []
        for nid in validation.supporting_evidence_ids:
            node = self.graph_repo.get_node(nid)
            if node and (node.as_of.replace(tzinfo=timezone.utc) if node.as_of.tzinfo is None else node.as_of) <= as_of:
                supporting_nodes.append(node)

        # 1. Replication Analysis
        rep_assessment = self.rep_analyzer.analyze(supporting_nodes)
        
        # 2. Generalization
        gen_state = self.strength_analyzer.analyze_generalization(supporting_nodes)
        
        # 3. Evidence Strength
        strength, explanation, insufficient = self.strength_analyzer.assess_strength(validation, rep_assessment, gen_state)
        
        assessment_id = self._deterministic_hash(f"rep_{validation.validation_id}_{as_of.timestamp()}")
        
        res = ResearchReplicationResult(
            assessment_id=assessment_id,
            hypothesis_id=validation.hypothesis_id,
            validation_id=validation.validation_id,
            research_identity=validation.research_identity,
            replication=rep_assessment,
            generalization_state=gen_state,
            evidence_strength=strength,
            explanation=explanation,
            falsification_respected=True,
            insufficient_sample_flag=insufficient,
            methodology_version="replication_v1",
            as_of=as_of,
            created_at=datetime.now(timezone.utc)
        )
        self.repo.save_result(res)
        return res
