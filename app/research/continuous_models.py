from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime
import json

class ResearchCycleState(str, Enum):
    IDLE = "IDLE"
    DISCOVERING = "DISCOVERING"
    WAITING_FOR_RESEARCH_APPROVAL = "WAITING_FOR_RESEARCH_APPROVAL"
    EXECUTING_EXPERIMENTS = "EXECUTING_EXPERIMENTS"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"

class ResearchCycle(BaseModel):
    cycle_id: str
    state: ResearchCycleState = ResearchCycleState.IDLE
    methodology_version: str = "continuous_research_v1"
    
    # State tracking
    generated_proposal_ids: List[str] = Field(default_factory=list)
    completed_proposal_ids: List[str] = Field(default_factory=list)
    
    # Budgets
    max_proposals: int = 5
    
    # Metadata
    failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
