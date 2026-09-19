from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class StrategyHealthState(str, Enum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    DATA_QUALITY_ISSUE = "DATA_QUALITY_ISSUE"

class PaperObservation(BaseModel):
    observation_id: str
    track_record_id: str
    validation_id: str
    
    observation_start: datetime
    observation_end: datetime
    
    starting_equity: float
    ending_equity: float
    net_pnl: float
    trade_count: int
    win_rate: float
    profit_factor: float
    drawdown_pct: float
    
    regime_distribution: Dict[str, Any] = Field(default_factory=dict)
    drift_state: str
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaperHealthHistory(BaseModel):
    history_id: str
    track_record_id: str
    previous_state: StrategyHealthState
    new_state: StrategyHealthState
    trigger_observation_id: str
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaperTrackRecord(BaseModel):
    track_record_id: str
    identity_hash: str
    frozen_specification_hash: str
    
    initial_equity: float = 10000.0
    current_equity: float = 10000.0
    cumulative_pnl: float = 0.0
    cumulative_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    
    observation_count: int = 0
    current_health_state: StrategyHealthState = StrategyHealthState.INSUFFICIENT_HISTORY
    
    first_observation_start: Optional[datetime] = None
    last_observation_end: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
