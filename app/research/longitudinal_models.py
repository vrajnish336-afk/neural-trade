from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum

from app.research.portfolio_models import ResearchCandidateSnapshot

class LongitudinalEventType(str, Enum):
    CANDIDATE_DISCOVERED = "CANDIDATE_DISCOVERED"
    CONCLUSION_CHANGED = "CONCLUSION_CHANGED"
    FORWARD_OBSERVATION_ADDED = "FORWARD_OBSERVATION_ADDED"
    HEALTH_CHANGED = "HEALTH_CHANGED"
    CONFLICT_OPENED = "CONFLICT_OPENED"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
    OPPORTUNITY_OPENED = "OPPORTUNITY_OPENED"
    OPPORTUNITY_RESOLVED = "OPPORTUNITY_RESOLVED"
    DRIFT_DETECTED = "DRIFT_DETECTED"

class StateTransition(BaseModel):
    field_name: str
    previous_state: str
    new_state: str
    reason: str

class LongitudinalEvent(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: LongitudinalEventType
    source_record_id: str
    transitions: List[StateTransition]
    
    # State immediately after the event
    resulting_snapshot: Optional[ResearchCandidateSnapshot] = None

class CandidateTimeline(BaseModel):
    identity_hash: str
    events: List[LongitudinalEvent]
    latest_snapshot: Optional[ResearchCandidateSnapshot]
    
    # Pre-calculated aggregations for UI
    total_forward_observations: int
    health_transitions_count: int
    priority_transitions_count: int
    as_of: Optional[datetime] = None
