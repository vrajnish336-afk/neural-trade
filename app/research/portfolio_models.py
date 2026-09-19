from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

from app.research.track_record_models import StrategyHealthState
from app.research.decision_models import ResearchDecisionState
from app.research.forward_validation_models import ForwardDriftState
from app.research.comparator import ComparabilityStatus

class ResearchPriority(str, Enum):
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    BLOCKED = "BLOCKED"

class ResearchEvidenceScore(BaseModel):
    total_score: int
    historical_evidence_score: int
    forward_evidence_score: int
    health_score: int
    penalty_score: int

class ResearchCandidateSnapshot(BaseModel):
    identity_hash: str
    canonical_hypothesis: str
    strategy: str
    symbols: List[str]
    timeframe: str
    
    # Evidence Dimensions
    forward_observation_count: int
    current_health: StrategyHealthState
    latest_drift: ForwardDriftState
    decision_state: ResearchDecisionState
    
    # Financial Metrics (For context, NOT for sole ranking)
    cumulative_forward_pnl: float
    max_forward_drawdown_pct: float
    
    # Metadata
    unresolved_conflicts: int
    open_opportunities: int
    missing_lineage: bool
    
    # Prioritization
    priority: ResearchPriority
    priority_reasons: List[str]
    evidence_score: ResearchEvidenceScore
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CandidateComparisonMatrix(BaseModel):
    comparability: ComparabilityStatus
    candidates: List[ResearchCandidateSnapshot]
    differences: List[str]
    conclusion: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
