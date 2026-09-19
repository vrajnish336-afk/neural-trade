from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge

class KnowledgePath(BaseModel):
    source_node: EvidenceNode
    target_node: EvidenceNode
    edges: List[EvidenceEdge] = Field(default_factory=list)
    nodes: List[EvidenceNode] = Field(default_factory=list)
    explanation: str = ""
    as_of: datetime

class KnowledgeCluster(BaseModel):
    cluster_id: str
    cluster_name: str
    nodes: List[EvidenceNode] = Field(default_factory=list)
    edges: List[EvidenceEdge] = Field(default_factory=list)
    as_of: datetime

class GraphSummary(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    supported_relationships: int = 0
    conflicted_relationships: int = 0
    conditional_relationships: int = 0
    unresolved_gaps: int = 0
    recurring_failure_clusters: int = 0
    as_of: datetime
