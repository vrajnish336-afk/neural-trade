from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Set
from enum import Enum
from datetime import datetime

class KnowledgeState(str, Enum):
    ESTABLISHED_WITHIN_BOUNDARY = "ESTABLISHED_WITHIN_BOUNDARY"
    SUPPORTED = "SUPPORTED"
    CONDITIONALLY_SUPPORTED = "CONDITIONALLY_SUPPORTED"
    WEAKENED = "WEAKENED"
    CONFLICTED = "CONFLICTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    STALE = "STALE"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"

class PatternFamily(str, Enum):
    DATASET = "DATASET"
    REGIME = "REGIME"
    TIMEFRAME = "TIMEFRAME"
    METHODOLOGY = "METHODOLOGY"
    COST = "COST"
    STRATEGY_FAMILY = "STRATEGY_FAMILY"
    REPRODUCTION_STATUS = "REPRODUCTION_STATUS"
    DISCREPANCY_TYPE = "DISCREPANCY_TYPE"
    ISOLATION_FACTOR = "ISOLATION_FACTOR"
    EVIDENCE_STRENGTH = "EVIDENCE_STRENGTH"
    HEALTH_STATE = "HEALTH_STATE"
    PORTFOLIO_FAILURE_MODE = "PORTFOLIO_FAILURE_MODE"
    FORECAST_EVALUATION_STATE = "FORECAST_EVALUATION_STATE"

class KnowledgeScope(BaseModel):
    dataset_scope: List[str] = Field(default_factory=list)
    timeframe_scope: List[str] = Field(default_factory=list)
    regime_scope: List[str] = Field(default_factory=list)
    methodology_scope: List[str] = Field(default_factory=list)
    cost_scope: List[str] = Field(default_factory=list)
    
class ResearchKnowledgeClaim(BaseModel):
    claim_id: str
    canonical_statement: str
    knowledge_state: KnowledgeState
    scope: KnowledgeScope
    evidence_ids: List[str] = Field(default_factory=list)
    source_experiment_ids: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    independent_evidence_count: int = 0
    evidence_strength: str = "UNKNOWN"
    consensus_state: str = "UNKNOWN"
    conflict_state: str = "UNKNOWN"
    decay_state: str = "UNKNOWN"
    drift_state: str = "UNKNOWN"
    limitations: List[str] = Field(default_factory=list)
    methodology_version: str = "knowledge_v1"
    as_of: datetime
    created_at: datetime

class KnowledgePattern(BaseModel):
    pattern_id: str
    pattern_family: PatternFamily
    description: str
    independent_evidence_count: int
    supporting_evidence_units: int
    contradicting_evidence_units: int
    datasets_involved: List[str] = Field(default_factory=list)
    regimes_involved: List[str] = Field(default_factory=list)
    methodologies_involved: List[str] = Field(default_factory=list)
    timeframes_involved: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    methodology_version: str = "pattern_v1"
    as_of: datetime
    created_at: datetime

class KnowledgeGap(BaseModel):
    gap_id: str
    claim_id: Optional[str] = None
    description: str
    reason: str
    required_evidence_type: str
    as_of: datetime
    created_at: datetime
