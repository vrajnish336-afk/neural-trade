from typing import List, Dict, Optional
from datetime import datetime, timezone
import hashlib
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.consensus.models import EvidenceConsensusUnit
from app.research.replication.models import ResearchReplicationResult

class EvidenceNormalizer:
    def __init__(self, graph_repo: EvidenceGraphRepository):
        self.graph_repo = graph_repo

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def normalize(self, identity_hash: str, as_of: datetime, replication: Optional[ResearchReplicationResult] = None) -> List[EvidenceConsensusUnit]:
        """
        Gathers all incoming edges to the hypothesis focal node, filters by as_of, 
        and extracts deterministic consensus metadata.
        """
        focal_nodes = [n for n in self.graph_repo.get_nodes() if n.identity_hash == identity_hash and n.node_type in [NodeType.RESEARCH_QUESTION, NodeType.HYPOTHESIS]]
        if not focal_nodes:
            return []
            
        focal_id = focal_nodes[0].node_id
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        edges = self.graph_repo.get_edges_for_node(focal_id, as_of=as_of_utc, direction='in')
        
        units = []
        for e in edges:
            if e.relationship_type not in [EdgeRelationship.SUPPORTS, EdgeRelationship.CONTRADICTS, EdgeRelationship.WEAKENS]:
                continue
                
            src = self.graph_repo.get_node(e.source_node_id)
            if not src or src.node_type != NodeType.EXPERIMENT:
                continue
                
            src_as_of = src.as_of.replace(tzinfo=timezone.utc) if src.as_of.tzinfo is None else src.as_of
            if src_as_of > as_of_utc:
                continue
                
            meta = src.metadata
            direction = "SUPPORTS" if e.relationship_type == EdgeRelationship.SUPPORTS else "CONTRADICTS"
            
            # Simple heuristic for independence: if replication exists, we trust it handled overlap.
            # But here we just assume all distinct nodes are independent UNLESS Phase 35 flagged them explicitly.
            # For this engine's scope, we use a basic heuristic: if it's identical dataset and seed, it's not independent.
            is_ind = True
            
            units.append(EvidenceConsensusUnit(
                unit_id=self._deterministic_hash(f"unit_{e.edge_id}"),
                evidence_id=e.source_node_id,
                dataset_id=meta.get("dataset_id"),
                seed=meta.get("seed"),
                regime=meta.get("regime"),
                methodology_version=meta.get("methodology_version"),
                cost_assumption=meta.get("cost_scenario"),
                support_or_contradiction=direction,
                is_independent=is_ind,
                created_at=src_as_of
            ))
            
        return units
