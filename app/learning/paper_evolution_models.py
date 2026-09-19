from pydantic import BaseModel, Field
from typing import List, Optional, Any
from enum import Enum
from datetime import datetime

class PostMortemObservation(BaseModel):
    position_id: str
    symbol: str
    direction: str
    entry_time: datetime
    exit_time: datetime
    holding_duration_seconds: float
    realized_pnl: float
    is_win: bool
    exit_reason: str
    strategy: str = "UNKNOWN"
    regime: str = "UNKNOWN"
    mtf_alignment: str = "UNKNOWN"
    portfolio_correlation: str = "UNKNOWN"
    
class LessonState(str, Enum):
    VALIDATED = "VALIDATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"

class PaperResearchLesson(BaseModel):
    lesson_id: str
    source_trade_ids: List[str]
    strategy: str
    regime: str
    observation: str
    sample_count: int
    wins: int
    losses: int
    observed_pnl: float
    confidence_status: LessonState
    created_at: datetime
    data_window_start: datetime
    data_window_end: datetime
    mtf_alignment: str = "UNKNOWN"
    portfolio_correlation: str = "UNKNOWN"
    cross_asset_symbols: List[str] = Field(default_factory=list)
    
class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"
    EXPIRED = "EXPIRED"

class EvolutionProposal(BaseModel):
    proposal_id: str
    lesson_ids: List[str]
    evidence_ids: List[str]
    affected_strategy: str
    affected_parameter: str
    current_value: Any
    proposed_value: Any
    delta: Any
    reason: str
    evidence_summary: str
    sample_size: int
    validation_status: str
    expected_research_rationale: str
    created_at: datetime
    status: ProposalStatus
