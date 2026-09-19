from typing import List, Optional
from datetime import datetime
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, EdgeRelationship, ConclusionState

class GraphQueries:
    def __init__(self):
        self.repo = EvidenceGraphRepository()
        
    def get_evidence_chain(self, node_id: str, as_of: Optional[datetime] = None, max_depth: int = 5) -> List[EvidenceNode]:
        """Traverses DERIVED_FROM edges upstream to find lineage."""
        chain = []
        current_id = node_id
        depth = 0
        
        while current_id and depth < max_depth:
            node = self.repo.get_node(current_id)
            if not node:
                break
            if as_of and node.as_of > as_of:
                break
                
            chain.append(node)
            edges = self.repo.get_edges_for_node(current_id, as_of=as_of, direction='out')
            
            # Find DERIVED_FROM
            next_id = None
            for e in edges:
                if e.relationship_type == EdgeRelationship.DERIVED_FROM:
                    next_id = e.target_node_id
                    break
            current_id = next_id
            depth += 1
            
        return chain
        
    def get_supporting_evidence(self, node_id: str, as_of: Optional[datetime] = None) -> List[EvidenceNode]:
        edges = self.repo.get_edges_for_node(node_id, as_of=as_of, direction='in')
        supporting = []
        for e in edges:
            if e.relationship_type in (EdgeRelationship.SUPPORTS, EdgeRelationship.STRENGTHENS, EdgeRelationship.VALIDATES):
                src = self.repo.get_node(e.source_node_id)
                if src and (not as_of or src.as_of <= as_of):
                    supporting.append(src)
        return supporting
        
    def get_contradicting_evidence(self, node_id: str, as_of: Optional[datetime] = None) -> List[EvidenceNode]:
        edges = self.repo.get_edges_for_node(node_id, as_of=as_of, direction='in')
        contradicting = []
        for e in edges:
            if e.relationship_type in (EdgeRelationship.CONTRADICTS, EdgeRelationship.WEAKENS, EdgeRelationship.INVALIDATES):
                src = self.repo.get_node(e.source_node_id)
                if src and (not as_of or src.as_of <= as_of):
                    contradicting.append(src)
        return contradicting

    def validate_graph(self) -> dict:
        nodes = self.repo.get_nodes()
        edges = self.repo.get_edges()
        
        node_ids = {n.node_id for n in nodes}
        orphans = 0
        missing_targets = 0
        
        for e in edges:
            if e.source_node_id not in node_ids:
                orphans += 1
            if e.target_node_id not in node_ids:
                missing_targets += 1
                
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "orphan_edges": orphans,
            "missing_targets": missing_targets,
            "status": "VALID" if orphans == 0 and missing_targets == 0 else "INVALID"
        }
