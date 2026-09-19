import uuid
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class PortfolioEligibilityStatus(str, Enum):
    ELIGIBLE_FOR_PORTFOLIO_RESEARCH = "ELIGIBLE_FOR_PORTFOLIO_RESEARCH"
    WATCH = "WATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DEGRADED = "DEGRADED"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"

class DiversificationAssessment(str, Enum):
    STRONG_DIVERSIFICATION_EVIDENCE = "STRONG_DIVERSIFICATION_EVIDENCE"
    MODERATE_DIVERSIFICATION_EVIDENCE = "MODERATE_DIVERSIFICATION_EVIDENCE"
    CONDITIONAL_DIVERSIFICATION = "CONDITIONAL_DIVERSIFICATION"
    WEAK_DIVERSIFICATION = "WEAK_DIVERSIFICATION"
    NO_DIVERSIFICATION_EVIDENCE = "NO_DIVERSIFICATION_EVIDENCE"
    CONCENTRATED_DOWNSIDE = "CONCENTRATED_DOWNSIDE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class PortfolioResearchAssessment(str, Enum):
    ROBUST_PORTFOLIO_EVIDENCE = "ROBUST_PORTFOLIO_EVIDENCE"
    CONDITIONAL_PORTFOLIO_EVIDENCE = "CONDITIONAL_PORTFOLIO_EVIDENCE"
    FRAGILE_PORTFOLIO_EVIDENCE = "FRAGILE_PORTFOLIO_EVIDENCE"
    INCONSISTENT_PORTFOLIO = "INCONSISTENT_PORTFOLIO"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTED = "CONFLICTED"

class CorrelationResult(BaseModel):
    pearson_correlation: Optional[float] = None
    spearman_correlation: Optional[float] = None
    drawdown_overlap_pct: Optional[float] = None
    sample_size: int
    is_statistically_significant: bool = False

class PortfolioResearchSnapshot(BaseModel):
    portfolio_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate_ids: List[str]
    dataset_identity: str
    common_start: datetime
    common_end: datetime
    weights: Dict[str, float]
    cost_model: dict
    risk_model: dict
    as_of: datetime
    seed: int = 42
    
    correlation_matrix: Dict[str, Dict[str, CorrelationResult]]
    diversification_state: DiversificationAssessment
    research_assessment: PortfolioResearchAssessment
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
