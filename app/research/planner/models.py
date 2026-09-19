from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class ResearchDecisionState(str, Enum):
    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    RANKED = "RANKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    QUEUED = "QUEUED"
    SUPERSEDED = "SUPERSEDED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DATA_NOT_AVAILABLE = "DATA_NOT_AVAILABLE"

class ResearchAction(str, Enum):
    RESEARCH_NOW = "RESEARCH_NOW"
    RESEARCH_LATER = "RESEARCH_LATER"
    REVALIDATE = "REVALIDATE"
    RESOLVE_CONFLICT = "RESOLVE_CONFLICT"
    COLLECT_DATA = "COLLECT_DATA"
    NO_ACTION = "NO_ACTION"
    ALREADY_RESEARCHED = "ALREADY_RESEARCHED"

class ResearchPriorityBreakdown(BaseModel):
    evidence_gap_weight: float = 0.0
    uncertainty_weight: float = 0.0
    conflict_weight: float = 0.0
    information_gain_weight: float = 0.0
    feasibility_weight: float = 0.0
    novelty_weight: float = 0.0
    reproducibility_weight: float = 0.0
    redundancy_penalty: float = 0.0
    evidence_saturation_penalty: float = 0.0
    expected_information_value_heuristic: float = 0.0
    final_score: float = 0.0
    explanation: str = ""
    evidence_references: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    methodology_version: str = "planner_v1"

class ResearchQuestionCandidate(BaseModel):
    question_id: str
    research_identity: str
    research_question: str
    hypothesis_reference: Optional[str] = None
    originating_gap: Optional[str] = None
    related_experiments: List[str] = Field(default_factory=list)
    related_lessons: List[str] = Field(default_factory=list)
    related_conclusions: List[str] = Field(default_factory=list)
    evidence_strength: float = 0.0
    evidence_gaps: List[str] = Field(default_factory=list)
    conflict_count: int = 0
    sample_size_state: str = "UNKNOWN"
    forward_validation_state: str = "UNKNOWN"
    robustness_state: str = "UNKNOWN"
    regime_coverage: str = "UNKNOWN"
    parameter_stability: str = "UNKNOWN"
    cost_resilience: str = "UNKNOWN"
    novelty: float = 0.0
    expected_information_gain: float = 0.0
    research_value: float = 0.0
    priority_score: float = 0.0
    priority_reason: str = ""
    methodology_version: str = "planner_v1"
    created_at: datetime
    as_of: datetime
    status: ResearchDecisionState

class ResearchDecision(BaseModel):
    decision_id: str
    research_question_id: str
    recommended_action: ResearchAction
    priority: float
    priority_breakdown: ResearchPriorityBreakdown
    evidence_summary: str = ""
    evidence_gap_summary: str = ""
    conflict_summary: str = ""
    feasibility: str = "UNKNOWN"
    expected_information_value: float = 0.0
    required_experiment_type: str = "UNKNOWN"
    validation_requirements: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    rationale: str = ""
    status: ResearchDecisionState
    created_at: datetime
    as_of: datetime
    approval_timestamp: Optional[datetime] = None
    methodology_version: str = "planner_v1"
