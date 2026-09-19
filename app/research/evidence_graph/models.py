from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class NodeType(str, Enum):
    RESEARCH_QUESTION = "RESEARCH_QUESTION"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT = "EXPERIMENT"
    DATASET = "DATASET"
    OBSERVATION = "OBSERVATION"
    FORECAST = "FORECAST"
    FORWARD_VALIDATION = "FORWARD_VALIDATION"
    ROBUSTNESS_RESULT = "ROBUSTNESS_RESULT"
    LESSON = "LESSON"
    CONCLUSION = "CONCLUSION"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    EVOLUTION_PROPOSAL = "EVOLUTION_PROPOSAL"
    KNOWLEDGE_CHANGE = "KNOWLEDGE_CHANGE"
    WORLD_OBSERVATION = "WORLD_OBSERVATION"
    HEALTH_STATE = "HEALTH_STATE"
    EXPERIMENT_COMPARISON = "EXPERIMENT_COMPARISON"
    KNOWLEDGE_CLAIM = "KNOWLEDGE_CLAIM"
    KNOWLEDGE_PATTERN = "KNOWLEDGE_PATTERN"
    RESEARCH_GAP = "RESEARCH_GAP"
    STRATEGY_FAMILY = "STRATEGY_FAMILY"
    REGIME = "REGIME"
    TIMEFRAME = "TIMEFRAME"
    METHODOLOGY = "METHODOLOGY"
    COST_ASSUMPTION = "COST_ASSUMPTION"
    DISCREPANCY = "DISCREPANCY"
    REVALIDATION = "REVALIDATION"
    PORTFOLIO_FAILURE_MODE = "PORTFOLIO_FAILURE_MODE"
    FORECAST_FINDING = "FORECAST_FINDING"
    WORLD_INTELLIGENCE_CONTEXT = "WORLD_INTELLIGENCE_CONTEXT"

class EdgeRelationship(str, Enum):
    DERIVED_FROM = "DERIVED_FROM"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    WEAKENS = "WEAKENS"
    STRENGTHENS = "STRENGTHENS"
    VALIDATES = "VALIDATES"
    INVALIDATES = "INVALIDATES"
    SUPERSEDES = "SUPERSEDES"
    REFINES = "REFINES"
    DEPENDS_ON = "DEPENDS_ON"
    RELATED_TO = "RELATED_TO"
    CONDITIONED_ON = "CONDITIONED_ON"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    REPEATS = "REPEATS"
    REVALIDATES = "REVALIDATES"
    GENERALIZES_WITHIN = "GENERALIZES_WITHIN"
    LIMITED_BY = "LIMITED_BY"
    REQUIRES_RESEARCH = "REQUIRES_RESEARCH"
    FALSIFIES = "FALSIFIES"
    EXPOSES_GAP = "EXPOSES_GAP"
    SHARES_FAILURE_MODE = "SHARES_FAILURE_MODE"
    SHARES_REGIME = "SHARES_REGIME"
    SHARES_TIMEFRAME = "SHARES_TIMEFRAME"
    SHARES_METHODOLOGY = "SHARES_METHODOLOGY"
    SHARES_DATASET_BOUNDARY = "SHARES_DATASET_BOUNDARY"

class ConclusionState(str, Enum):
    UNTESTED = "UNTESTED"
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONFLICTED = "CONFLICTED"
    WEAKENED = "WEAKENED"
    STRENGTHENED = "STRENGTHENED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class EvidenceNode(BaseModel):
    node_id: str
    node_type: NodeType
    source_id: str
    source_type: str
    identity_hash: Optional[str] = None
    created_at: datetime
    observed_at: Optional[datetime] = None
    as_of: datetime
    methodology_version: str = "graph_v1"
    metadata: Dict = Field(default_factory=dict)

class EvidenceEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: EdgeRelationship
    evidence_basis: str
    confidence: float = 1.0
    methodology_version: str = "graph_v1"
    created_at: datetime
    as_of: datetime
    deterministic_key: str

class EvidenceStrengthProfile(BaseModel):
    dimensions: Dict[str, float] = Field(default_factory=dict)
    available_evidence_count: int = 0
    missing_evidence_count: int = 0
    conflicts_count: int = 0
    methodology_version: str = "graph_v1"
    explanation: str = ""
    conclusion_state: ConclusionState = ConclusionState.UNTESTED
