from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class MonitoringCycleStatus(str):
    COMPLETED = "COMPLETED"
    NO_CHANGES = "NO_CHANGES"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

class MonitoringCycleResult(BaseModel):
    cycle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = MonitoringCycleStatus.NO_CHANGES
    
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    validations_discovered: int = 0
    observations_recorded: int = 0
    duplicates_skipped: int = 0
    health_transitions: int = 0
    opportunities_created: int = 0
    knowledge_updates: int = 0
    errors: int = 0
    
    error_messages: List[str] = Field(default_factory=list)
    track_records_touched: List[str] = Field(default_factory=list)
