from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime

class ConclusionType(str, Enum):
    SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"
    CONDITIONAL_INFERENCE = "CONDITIONAL_INFERENCE"
    CONFLICTED_INFERENCE = "CONFLICTED_INFERENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RESEARCH_HYPOTHESIS = "RESEARCH_HYPOTHESIS"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"
    REQUIRES_REPLICATION = "REQUIRES_REPLICATION"
    REQUIRES_SCOPE_EXPANSION = "REQUIRES_SCOPE_EXPANSION"
    REQUIRES_INTERACTION_TEST = "REQUIRES_INTERACTION_TEST"

class ReasoningStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    FRAGILE = "FRAGILE"
    WEAK = "WEAK"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT = "INSUFFICIENT"

class ReasoningUncertainty(str, Enum):
    LOW_UNCERTAINTY = "LOW_UNCERTAINTY"
    CONDITIONAL_UNCERTAINTY = "CONDITIONAL_UNCERTAINTY"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    STALE = "STALE"
    SCOPE_LIMITED = "SCOPE_LIMITED"
    METHODOLOGY_LIMITED = "METHODOLOGY_LIMITED"

class ResearchReasoningResult(BaseModel):
    reasoning_id: str
    rule_id: str
    conclusion_type: ConclusionType
    canonical_statement: str
    source_claim_ids: List[str] = Field(default_factory=list)
    source_relationship_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    supporting_ids: List[str] = Field(default_factory=list)
    contradicting_ids: List[str] = Field(default_factory=list)
    scope_limitations: List[str] = Field(default_factory=list)
    reasoning_strength: ReasoningStrength
    uncertainty_state: ReasoningUncertainty
    research_gap_ids: List[str] = Field(default_factory=list)
    research_question_ids: List[str] = Field(default_factory=list)
    explanation_trace: str = ""
    as_of: datetime
    methodology_version: str = "reasoning_v1"
    created_at: datetime

class ResearchReasoningSummary(BaseModel):
    total_reasoning_results: int = 0
    supported_inferences: int = 0
    conditional_inferences: int = 0
    conflicted_inferences: int = 0
    insufficient_evidence: int = 0
    revalidation_required: int = 0
    replication_required: int = 0
    scope_expansion_required: int = 0
    interaction_tests_required: int = 0
    research_gap_count: int = 0
    as_of: datetime
