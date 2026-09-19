import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Set
import logging
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.queries import GraphQueries
from app.research.evidence_graph.models import NodeType, EdgeRelationship, EvidenceNode
from app.research.synthesis.models import KnowledgeSynthesis, KnowledgeState
from app.research.synthesis.repository import SynthesisRepository

logger = logging.getLogger(__name__)

class ResearchKnowledgeSynthesizer:
    def __init__(self, max_depth: int = 5, max_nodes: int = 200):
        self.repo = SynthesisRepository()
        self.graph_repo = EvidenceGraphRepository()
        self.graph_queries = GraphQueries()
        self.max_depth = max_depth
        self.max_nodes = max_nodes

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def synthesize(self, research_identity: str, as_of: Optional[datetime] = None) -> Optional[KnowledgeSynthesis]:
        """Aggregates all evidence for a given research identity up to as_of."""
        if not as_of:
            as_of = datetime.now(timezone.utc)
            
        # Find the origin node for this identity
        # Typically a RESEARCH_QUESTION or HYPOTHESIS node in the graph
        all_nodes = self.graph_repo.get_nodes(as_of=as_of)
        target_nodes = [n for n in all_nodes if n.identity_hash == research_identity]
        
        if not target_nodes:
            # Identity might just be the string itself
            # We can still synthesize by searching for experiments linked to it conceptually, 
            # but usually it's in the graph.
            return None
            
        # We'll use the first target node as the focal point
        focal_node = target_nodes[0]
        
        supporting_nodes = []
        contradicting_nodes = []
        gaps = []
        visited = set()
        edges_used = set()
        
        # Traverse bounded
        self._traverse_evidence(focal_node.node_id, supporting_nodes, contradicting_nodes, gaps, visited, edges_used, as_of, 0)
        
        support_count = len([n for n in supporting_nodes if n.node_type == NodeType.EXPERIMENT])
        conflict_count = len([n for n in contradicting_nodes if n.node_type == NodeType.EXPERIMENT])
        
        state = KnowledgeState.INSUFFICIENT_EVIDENCE
        if support_count > 3 and conflict_count == 0:
            state = KnowledgeState.SUPPORTED
        elif support_count > 0 and conflict_count == 0:
            state = KnowledgeState.EMERGING
        elif support_count > 0 and conflict_count > 0:
            if support_count > conflict_count:
                state = KnowledgeState.PARTIALLY_SUPPORTED
            else:
                state = KnowledgeState.CONFLICTED
        elif conflict_count > support_count:
            state = KnowledgeState.WEAKENED
            
        # Check staleness
        if support_count > 0:
            latest_exp = max(n.created_at for n in supporting_nodes if n.node_type == NodeType.EXPERIMENT)
            if (as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of).timestamp() - (latest_exp.replace(tzinfo=timezone.utc) if latest_exp.tzinfo is None else latest_exp).timestamp() > 90 * 86400:
                state = KnowledgeState.STALE
                
        syn_id = self._deterministic_hash(f"syn_{research_identity}_{len(visited)}_{as_of.timestamp()}")
        
        syn = KnowledgeSynthesis(
            synthesis_id=syn_id,
            research_identity=research_identity,
            topic=f"Synthesis for {research_identity}",
            known_findings=[f"Found {support_count} supporting experiments."],
            supporting_evidence=[n.node_id for n in supporting_nodes],
            contradictory_evidence=[n.node_id for n in contradicting_nodes],
            evidence_gaps=[n.node_id for n in gaps],
            confidence_state=state,
            as_of=as_of,
            source_node_ids=list(visited),
            source_edge_ids=list(edges_used)
        )
        
        self.repo.save_synthesis(syn)
        return syn

    def _traverse_evidence(self, node_id: str, support: List[EvidenceNode], contradict: List[EvidenceNode], gaps: List[EvidenceNode], visited: Set[str], edges_used: Set[str], as_of: datetime, depth: int):
        if depth >= self.max_depth or len(visited) >= self.max_nodes:
            return
        if node_id in visited:
            return
        visited.add(node_id)
        
        node = self.graph_repo.get_node(node_id)
        if not node or (node.as_of.replace(tzinfo=timezone.utc) if node.as_of.tzinfo is None else node.as_of) > (as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of):
            return
            
        if node.node_type == NodeType.EVIDENCE_GAP:
            gaps.append(node)
            
        edges = self.graph_repo.get_edges_for_node(node_id, as_of=as_of, direction='in')
        for e in edges:
            if e.edge_id in edges_used: continue
            edges_used.add(e.edge_id)
            
            src = self.graph_repo.get_node(e.source_node_id)
            if not src or (src.as_of.replace(tzinfo=timezone.utc) if src.as_of.tzinfo is None else src.as_of) > (as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of):
                continue
                
            if e.relationship_type in [EdgeRelationship.SUPPORTS, EdgeRelationship.STRENGTHENS, EdgeRelationship.VALIDATES]:
                if src not in support:
                    support.append(src)
            elif e.relationship_type in [EdgeRelationship.CONTRADICTS, EdgeRelationship.WEAKENS, EdgeRelationship.INVALIDATES]:
                if src not in contradict:
                    contradict.append(src)
                    
            self._traverse_evidence(e.source_node_id, support, contradict, gaps, visited, edges_used, as_of, depth + 1)
