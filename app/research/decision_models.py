from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class ResearchConfidenceState(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    UNRESOLVED = "UNRESOLVED"

class ResearchDecisionState(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RESEARCH_LIMITED = "RESEARCH_LIMITED"
    MIXED_EVIDENCE = "MIXED_EVIDENCE"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    SUPPORTED_FOR_FURTHER_RESEARCH = "SUPPORTED_FOR_FURTHER_RESEARCH"
    RESEARCH_RESULT_SUPPORTED = "RESEARCH_RESULT_SUPPORTED"
    SOFTWARE_OR_ACCOUNTING_ISSUE = "SOFTWARE_OR_ACCOUNTING_ISSUE"
    BLOCKED = "BLOCKED"

class NextResearchAction(str, Enum):
    COLLECT_MORE_DATA = "COLLECT_MORE_DATA"
    OBTAIN_OOS_OBSERVATIONS = "OBTAIN_OOS_OBSERVATIONS"
    EVALUATE_ANOTHER_SEED = "EVALUATE_ANOTHER_SEED"
    TEST_ANOTHER_REGIME = "TEST_ANOTHER_REGIME"
    RUN_COST_STRESS = "RUN_COST_STRESS"
    VALIDATE_WALK_FORWARD = "VALIDATE_WALK_FORWARD"
    INVESTIGATE_ACCOUNTING = "INVESTIGATE_ACCOUNTING"
    INSPECT_CONFLICTING_EXPERIMENTS = "INSPECT_CONFLICTING_EXPERIMENTS"
    NONE_REQUIRED = "NONE_REQUIRED"

class RelationshipType(str, Enum):
    DUPLICATES = "DUPLICATES"
    RELATED_TO = "RELATED_TO"
    EXTENDS = "EXTENDS"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    DERIVED_FROM = "DERIVED_FROM"
    REQUIRES_MORE_DATA = "REQUIRES_MORE_DATA"

class ResearchRelationship(BaseModel):
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    description: str

class ResearchConflict(BaseModel):
    conflict_id: str
    identity_hash: str
    experiment_id_1: str
    experiment_id_2: str
    conflict_type: str
    severity: str # e.g. "HIGH", "MEDIUM"
    explanation: str
    resolution_status: str = "UNRESOLVED"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ResearchConclusion(BaseModel):
    conclusion_id: str
    identity_hash: str
    
    decision_state: ResearchDecisionState
    confidence_state: ResearchConfidenceState
    
    summary: str
    supporting_evidence_count: int
    conflicting_evidence_count: int
    
    limitations: List[str]
    next_research_action: NextResearchAction
    
    ai_explanation: Optional[str] = None
    
    provenance_experiment_ids: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
