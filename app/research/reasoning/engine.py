from datetime import datetime, timezone
from typing import List, Dict, Optional
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.knowledge_intelligence.models import ResearchKnowledgeClaim, KnowledgeState
from app.research.reasoning.models import ResearchReasoningResult
from app.research.reasoning.rules import RULES

class ReasoningEngine:
    def __init__(self, graph_repo: EvidenceGraphRepository):
        self.graph_repo = graph_repo
        self.rules = RULES

    def reason_over_neighborhood(self, root_claim: ResearchKnowledgeClaim, as_of: datetime, max_depth: int = 2) -> List[ResearchReasoningResult]:
        """Performs bounded reasoning traversal over a root claim's neighborhood."""
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # 1. Bounded traversal to get neighborhood nodes and edges
        visited_nodes = set()
        visited_edges = set()
        edges_list = []
        
        def _traverse(current_id: str, depth: int):
            if depth >= max_depth or current_id in visited_nodes:
                return
            visited_nodes.add(current_id)
            
            edges_out = self.graph_repo.get_edges_for_node(current_id, as_of=as_of_utc, direction='out')
            edges_in = self.graph_repo.get_edges_for_node(current_id, as_of=as_of_utc, direction='in')
            
            for e in edges_out + edges_in:
                if e.edge_id not in visited_edges:
                    visited_edges.add(e.edge_id)
                    edges_list.append(e)
                    
                    next_id = e.target_node_id if e.source_node_id == current_id else e.source_node_id
                    _traverse(next_id, depth + 1)
        
        _traverse(root_claim.claim_id, 0)
        
        # 2. Extract Claims from neighborhood
        claims_list = [root_claim]
        for nid in visited_nodes:
            if nid == root_claim.claim_id:
                continue
            n = self.graph_repo.get_node(nid)
            if n and n.node_type == "KNOWLEDGE_CLAIM" and n.as_of <= as_of_utc:
                # Reconstruct mock claim from metadata for rule evaluation (thin mapping)
                st = KnowledgeState.ESTABLISHED_WITHIN_BOUNDARY
                try:
                    st = KnowledgeState(n.metadata.get("state"))
                except:
                    pass
                c = ResearchKnowledgeClaim(
                    claim_id=n.node_id,
                    canonical_statement=n.metadata.get("statement", "UNKNOWN"),
                    knowledge_state=st,
                    scope=root_claim.scope, # Mock scope for reasoning interface
                    as_of=n.as_of,
                    created_at=n.created_at
                )
                claims_list.append(c)
                
        # 3. Apply Rules
        results = []
        for rule in self.rules:
            res = rule.evaluate(claims_list, edges_list, as_of_utc)
            if res:
                results.append(res)
                
        return results
