from typing import Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class TimeframeHierarchy(BaseModel):
    higher_timeframe: str
    middle_timeframe: Optional[str] = None
    lower_timeframe: str

class CandleStatus(str):
    COMPLETED = "COMPLETED"
    IN_PROGRESS = "IN_PROGRESS"
    MISSING = "MISSING"
    INVALID = "INVALID"

class TimeframeState(BaseModel):
    timeframe: str
    timestamp: datetime
    close: float
    status: str = CandleStatus.COMPLETED
    trend_state: Optional[str] = None
    setup_state: Optional[str] = None

class MultiTimeframeContext(BaseModel):
    htf_state: TimeframeState
    mtf_state: Optional[TimeframeState] = None
    ltf_state: TimeframeState
    dataset_identity: str
    as_of: datetime

class TimeframeAblationResult(BaseModel):
    ablation_id: str
    candidate_id: str
    hierarchy: TimeframeHierarchy
    baseline_return_pct: float
    htf_only_return_pct: float
    htf_mtf_return_pct: float
    full_return_pct: float
    created_at: datetime
