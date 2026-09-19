from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class JobState(str, Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY_WAIT = "RETRY_WAIT"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"

class ResearchJob(BaseModel):
    job_id: str
    opportunity_id: str
    identity_hash: str
    
    priority: float = Field(default=0.0)
    state: JobState = JobState.QUEUED
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    claimed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    
    result_experiment_id: Optional[str] = None

class OrchestratorConfig(BaseModel):
    enabled: bool = True
    max_queue_size: int = 100
    max_jobs_per_cycle: int = 5
    max_retries: int = 3
    cooldown_seconds: int = 60
