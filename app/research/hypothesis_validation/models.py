from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class ValidationState(str, Enum):
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    REJECTED = "REJECTED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"
    NOT_ELIGIBLE_FOR_VALIDATION = "NOT_ELIGIBLE_FOR_VALIDATION"

class EvidenceClassification(str, Enum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    NEUTRAL = "NEUTRAL"
    INSUFFICIENT = "INSUFFICIENT"

class FalsificationState(str, Enum):
    NOT_TRIGGERED = "NOT_TRIGGERED"
    TRIGGERED = "TRIGGERED"
    UNDETERMINED = "UNDETERMINED"

class HypothesisValidationResult(BaseModel):
    validation_id: str
    hypothesis_id: str
    research_identity: str
    status: ValidationState = ValidationState.INCONCLUSIVE
    validation_state: ValidationState = ValidationState.INCONCLUSIVE
    evidence_state: EvidenceClassification = EvidenceClassification.INSUFFICIENT
    support_score: float = 0.0
    contradiction_score: float = 0.0
    evidence_count: int = 0
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    unresolved_evidence_ids: List[str] = Field(default_factory=list)
    falsification_triggered: FalsificationState = FalsificationState.UNDETERMINED
    falsification_reason: str = ""
    robustness_state: str = "UNKNOWN"
    generalization_state: str = "UNKNOWN"
    sample_size_state: str = "UNKNOWN"
    cost_resilience_state: str = "UNKNOWN"
    regime_coverage_state: str = "UNKNOWN"
    forward_validation_state: str = "UNKNOWN"
    explanation: str = ""
    methodology_version: str = "validation_v1"
    as_of: datetime
    created_at: datetime
