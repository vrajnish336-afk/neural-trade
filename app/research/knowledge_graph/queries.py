from datetime import datetime, timezone
from typing import List, Dict, Set, Optional
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship
from app.research.knowledge_graph.models import KnowledgePath, KnowledgeCluster, GraphSummary

class KnowledgeGraphQueries:
    def __init__(self, graph_repo: EvidenceGraphRepository):
        self.graph_repo = graph_repo

    def get_historical_graph_summary(self, as_of: datetime) -> GraphSummary:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        nodes = [n for n in self.graph_repo.get_nodes() if n.as_of <= as_of_utc and n.node_type in [
            NodeType.KNOWLEDGE_CLAIM, NodeType.KNOWLEDGE_PATTERN, NodeType.RESEARCH_GAP, 
            NodeType.REGIME, NodeType.DATASET, NodeType.STRATEGY_FAMILY, NodeType.EXPERIMENT
        ]]
        
        node_ids = {n.node_id for n in nodes}
        
        edges = []
        for n in nodes:
            for e in self.graph_repo.get_edges_for_node(n.node_id, as_of=as_of_utc, direction='out'):
                if e.target_node_id in node_ids:
                    edges.append(e)
                    
        conflicted = sum(1 for e in edges if e.relationship_type == EdgeRelationship.CONTRADICTS)
        conditional = sum(1 for e in edges if e.relationship_type == EdgeRelationship.CONDITIONED_ON)
        gaps = sum(1 for n in nodes if n.node_type == NodeType.RESEARCH_GAP)
        failures = sum(1 for e in edges if e.relationship_type == EdgeRelationship.SHARES_FAILURE_MODE)
        
        return GraphSummary(
            total_nodes=len(nodes),
            total_edges=len(edges),
            supported_relationships=sum(1 for e in edges if e.relationship_type == EdgeRelationship.SUPPORTS),
            conflicted_relationships=conflicted,
            conditional_relationships=conditional,
            unresolved_gaps=gaps,
            recurring_failure_clusters=failures,
            as_of=as_of_utc
        )

    def get_related_claims(self, claim_id: str, as_of: datetime, max_depth: int = 3, max_nodes: int = 100) -> List[KnowledgePath]:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        start_node = self.graph_repo.get_node(claim_id)
        if not start_node or start_node.as_of > as_of_utc:
            return []
            
        paths = []
        visited = set()
        
        def _dfs(current_id: str, current_path_nodes: List[EvidenceNode], current_path_edges: List[EvidenceEdge], depth: int):
            if depth >= max_depth or len(visited) >= max_nodes:
                return
            visited.add(current_id)
            
            edges_out = self.graph_repo.get_edges_for_node(current_id, as_of=as_of_utc, direction='out')
            edges_in = self.graph_repo.get_edges_for_node(current_id, as_of=as_of_utc, direction='in')
            
            for e in edges_out + edges_in:
                next_id = e.target_node_id if e.source_node_id == current_id else e.source_node_id
                if next_id in visited:
                    continue
                    
                next_node = self.graph_repo.get_node(next_id)
                if not next_node or next_node.as_of > as_of_utc:
                    continue
                
                # Exclude raw experiment nodes from this specific knowledge query unless they are explicitly bridged
                # Usually we want Knowledge claims and scopes.
                new_nodes = current_path_nodes + [next_node]
                new_edges = current_path_edges + [e]
                
                if next_node.node_type in [NodeType.KNOWLEDGE_CLAIM, NodeType.KNOWLEDGE_PATTERN, NodeType.RESEARCH_GAP, NodeType.REGIME, NodeType.DATASET, NodeType.STRATEGY_FAMILY, NodeType.EXPERIMENT]:
                    paths.append(KnowledgePath(
                        source_node=start_node,
                        target_node=next_node,
                        edges=new_edges,
                        nodes=new_nodes,
                        explanation=f"Found related node via {e.relationship_type.value}",
                        as_of=as_of_utc
                    ))
                
                _dfs(next_id, new_nodes, new_edges, depth + 1)
                
        _dfs(claim_id, [start_node], [], 0)
        return paths

    def get_failure_clusters(self, as_of: datetime) -> List[KnowledgeCluster]:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        patterns = [n for n in self.graph_repo.get_nodes() if n.node_type == NodeType.KNOWLEDGE_PATTERN and n.as_of <= as_of_utc]
        clusters = []
        
        for p in patterns:
            edges = self.graph_repo.get_edges_for_node(p.node_id, as_of=as_of_utc, direction='out')
            failure_edges = [e for e in edges if e.relationship_type == EdgeRelationship.SHARES_FAILURE_MODE]
            if failure_edges:
                cluster_nodes = [p]
                for e in failure_edges:
                    n = self.graph_repo.get_node(e.target_node_id)
                    if n and n.as_of <= as_of_utc:
                        cluster_nodes.append(n)
                
                clusters.append(KnowledgeCluster(
                    cluster_id=f"cluster_{p.node_id}",
                    cluster_name=f"Failure Cluster: {p.metadata.get('family', 'UNKNOWN')}",
                    nodes=cluster_nodes,
                    edges=failure_edges,
                    as_of=as_of_utc
                ))
                
        return clusters
