from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime
from app.research.replication.models import EvidenceStrengthLevel

class DecayState(str, Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"
    UNKNOWN = "UNKNOWN"

class RevalidationReason(str, Enum):
    EVIDENCE_TOO_OLD = "EVIDENCE_TOO_OLD"
    NEW_REGIME = "NEW_REGIME"
    PERFORMANCE_DRIFT = "PERFORMANCE_DRIFT"
    COST_DRIFT = "COST_DRIFT"
    DATASET_DRIFT = "DATASET_DRIFT"
    METHODOLOGY_CHANGED = "METHODOLOGY_CHANGED"
    NEW_CONTRADICTION = "NEW_CONTRADICTION"
    FALSIFICATION_WARNING = "FALSIFICATION_WARNING"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    INSUFFICIENT_INDEPENDENT_REPLICATION = "INSUFFICIENT_INDEPENDENT_REPLICATION"
    MULTIPLE_TESTING_RISK = "MULTIPLE_TESTING_RISK"
    FORWARD_VALIDATION_STALE = "FORWARD_VALIDATION_STALE"

class RevalidationAssessmentState(str, Enum):
    REVALIDATION_CONFIRMS_ORIGINAL = "REVALIDATION_CONFIRMS_ORIGINAL"
    REVALIDATION_WEAKENS_ORIGINAL = "REVALIDATION_WEAKENS_ORIGINAL"
    REVALIDATION_CONFLICTS_WITH_ORIGINAL = "REVALIDATION_CONFLICTS_WITH_ORIGINAL"
    REVALIDATION_INCONCLUSIVE = "REVALIDATION_INCONCLUSIVE"
    REVALIDATION_NOT_ASSESSABLE = "REVALIDATION_NOT_ASSESSABLE"

class EvidenceDirection(str, Enum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    NEUTRAL = "NEUTRAL"
    INSUFFICIENT = "INSUFFICIENT"

class RevalidationAssessment(BaseModel):
    assessment_id: str
    hypothesis_id: str
    validation_id: str
    replication_assessment_id: Optional[str] = None
    research_identity: str
    
    evidence_age_days: Optional[float] = None
    decay_state: DecayState = DecayState.UNKNOWN
    
    drift_flags: List[str] = Field(default_factory=list)
    revalidation_reasons: List[RevalidationReason] = Field(default_factory=list)
    
    original_evidence_strength: EvidenceStrengthLevel = EvidenceStrengthLevel.INSUFFICIENT
    current_evidence_strength: EvidenceStrengthLevel = EvidenceStrengthLevel.INSUFFICIENT
    
    # Phase 50 Extension
    assessment_state: RevalidationAssessmentState = RevalidationAssessmentState.REVALIDATION_NOT_ASSESSABLE
    evidence_direction: EvidenceDirection = EvidenceDirection.INSUFFICIENT
    discrepancy_analysis_ids: List[str] = Field(default_factory=list)
    isolation_plan_ids: List[str] = Field(default_factory=list)
    
    explanation: str = ""
    revalidation_required: bool = False
    
    methodology_version: str = "revalidation_v2"
    as_of: datetime
    created_at: datetime
    limitations: List[str] = Field(default_factory=list)
