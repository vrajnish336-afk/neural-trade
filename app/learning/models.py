from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import json
import hashlib

class LessonState(str, Enum):
    OBSERVED = "OBSERVED"
    SUPPORTED = "SUPPORTED"
    MIXED_EVIDENCE = "MIXED_EVIDENCE"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"
    STALE = "STALE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class ProposalState(str, Enum):
    PROPOSED = "PROPOSED"
    UNDER_VALIDATION = "UNDER_VALIDATION"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class ResearchLesson(BaseModel):
    lesson_id: str
    identity_hash: str
    strategy: str
    regime: Optional[str] = None
    timeframe: Optional[str] = None
    
    lesson_statement: str
    evidence_count: int
    supporting_observation_ids: List[str] = Field(default_factory=list)
    conflicting_observation_ids: List[str] = Field(default_factory=list)
    
    confidence_score: float
    state: LessonState
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_observed_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_hash(self) -> str:
        data = f"{self.identity_hash}|{self.strategy}|{self.regime}|{self.lesson_statement}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

class ParameterProposal(BaseModel):
    proposal_id: str
    identity_hash: str
    strategy: str
    
    baseline_parameters_json: str
    proposed_parameters_json: str
    
    supporting_lesson_ids: List[str] = Field(default_factory=list)
    reason: str
    
    state: ProposalState = ProposalState.PROPOSED
    validation_run_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_hash(self) -> str:
        data = f"{self.identity_hash}|{self.strategy}|{self.baseline_parameters_json}|{self.proposed_parameters_json}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
