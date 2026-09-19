from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class WalkForwardType(str, Enum):
    ROLLING = "ROLLING"
    EXPANDING = "EXPANDING"

class WalkForwardWindowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NO_SIGNAL = "NO_SIGNAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class TemporalGeneralizationState(str, Enum):
    STRONG_TEMPORAL_GENERALIZATION = "STRONG_TEMPORAL_GENERALIZATION"
    MODERATE_TEMPORAL_GENERALIZATION = "MODERATE_TEMPORAL_GENERALIZATION"
    WEAK_TEMPORAL_GENERALIZATION = "WEAK_TEMPORAL_GENERALIZATION"
    FRAGILE_TEMPORAL_GENERALIZATION = "FRAGILE_TEMPORAL_GENERALIZATION"
    INCONSISTENT = "INCONSISTENT"
    INSUFFICIENT_WINDOWS = "INSUFFICIENT_WINDOWS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class WalkForwardWindow(BaseModel):
    window_id: str
    run_id: str
    candidate_id: str
    dataset_identity: str
    
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    forward_start: datetime
    forward_end: datetime
    
    methodology_version: str
    strategy_identity: str
    parameter_identity: str
    seed: Optional[str] = None
    
    status: WalkForwardWindowStatus = WalkForwardWindowStatus.PENDING
    trade_count: int = 0
    return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    cost_assumptions: Dict[str, float] = Field(default_factory=dict)
    regime_coverage: List[str] = Field(default_factory=list)
    
    as_of: datetime
    created_at: datetime
    lineage: str

class TemporalGeneralizationAssessment(BaseModel):
    assessment_id: str
    candidate_id: str
    run_id: str
    
    window_type: WalkForwardType
    total_windows: int
    successful_windows: int
    failed_windows: int
    zero_trade_windows: int
    
    performance_dispersion: float
    drawdown_dispersion: float
    trade_count_dispersion: float
    
    overall_state: TemporalGeneralizationState
    research_gaps: List[str] = Field(default_factory=list)
    
    as_of: datetime
    created_at: datetime
