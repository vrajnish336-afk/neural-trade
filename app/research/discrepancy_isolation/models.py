from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
from datetime import datetime
from app.research.reproduction.models import FrozenResearchSpecification
from app.research.reproduction_intelligence.models import ImpactLevel

class IsolationApprovalState(str, Enum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    REJECTED = "REJECTED"

class IsolationStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    ISOLATION_BOUNDED = "ISOLATION_BOUNDED"
    FAILED = "FAILED"

class RevalidationDecisionState(str, Enum):
    NO_REVALIDATION_REQUIRED = "NO_REVALIDATION_REQUIRED"
    REVIEW_RECOMMENDED = "REVIEW_RECOMMENDED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    RESEARCH_ARTIFACT_CHANGED = "RESEARCH_ARTIFACT_CHANGED"
    RESEARCH_CONCLUSION_REVIEW_REQUIRED = "RESEARCH_CONCLUSION_REVIEW_REQUIRED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"

class IsolationAttributionState(str, Enum):
    ISOLATION_SUPPORTED = "ISOLATION_SUPPORTED"
    PARTIAL_ISOLATION = "PARTIAL_ISOLATION"
    ISOLATION_UNRESOLVED = "ISOLATION_UNRESOLVED"
    INTERACTION_UNRESOLVED = "INTERACTION_UNRESOLVED"
    PENDING = "PENDING"

class IsolationExperiment(BaseModel):
    experiment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    target_factor: str
    baseline_value: str
    changed_value: str
    frozen_inputs_fingerprint: str
    changed_inputs_fingerprint: str
    status: IsolationStatus = IsolationStatus.PENDING
    reproduction_id: Optional[str] = None
    attribution: IsolationAttributionState = IsolationAttributionState.PENDING
    impact: ImpactLevel = ImpactLevel.NOT_ASSESSABLE
    lineage_ids: List[str] = Field(default_factory=list)

class DiscrepancyIsolationPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_reproduction_id: str
    source_discrepancy_analysis_id: str
    baseline_specification: FrozenResearchSpecification
    as_of: datetime = Field(default_factory=datetime.utcnow)
    candidate_factors: List[str] = Field(default_factory=list)
    experiments: List[IsolationExperiment] = Field(default_factory=list)
    max_experiments: int = 5
    status: IsolationStatus = IsolationStatus.PENDING
    approval_state: IsolationApprovalState = IsolationApprovalState.DRAFT
    expected_information_value: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class IsolationComparison(BaseModel):
    comparison_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str
    baseline_output_fingerprint: str
    experiment_output_fingerprint: str
    numerical_impact: ImpactLevel
    structural_impact: ImpactLevel
    attribution: IsolationAttributionState
    explanation: str

class RevalidationDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    state: RevalidationDecisionState
    explanation: str
    evidence_ids: List[str] = Field(default_factory=list)
