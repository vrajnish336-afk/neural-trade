from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
from datetime import datetime
import hashlib

class CompletenessState(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIALLY_REPRODUCIBLE = "PARTIALLY_REPRODUCIBLE"
    INSUFFICIENT_REPRODUCTION_DATA = "INSUFFICIENT_REPRODUCTION_DATA"
    NON_REPRODUCIBLE = "NON_REPRODUCIBLE"

class ReproducibilityState(str, Enum):
    REPRODUCIBLE = "REPRODUCIBLE"
    REPRODUCIBLE_WITH_SAME_INPUTS = "REPRODUCIBLE_WITH_SAME_INPUTS"
    INPUT_DATA_CHANGED = "INPUT_DATA_CHANGED"
    CONFIGURATION_CHANGED = "CONFIGURATION_CHANGED"
    METHODOLOGY_CHANGED = "METHODOLOGY_CHANGED"
    CODE_CHANGED = "CODE_CHANGED"
    DEPENDENCY_CHANGED = "DEPENDENCY_CHANGED"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    SOURCE_EVIDENCE_CHANGED = "SOURCE_EVIDENCE_CHANGED"
    INCOMPLETE_MANIFEST = "INCOMPLETE_MANIFEST"
    NON_REPRODUCIBLE = "NON_REPRODUCIBLE"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"

class ChangeCategory(str, Enum):
    DATA_CHANGED = "DATA_CHANGED"
    PARAMETERS_CHANGED = "PARAMETERS_CHANGED"
    STRATEGY_CHANGED = "STRATEGY_CHANGED"
    METHODOLOGY_CHANGED = "METHODOLOGY_CHANGED"
    CODE_CHANGED = "CODE_CHANGED"
    DEPENDENCIES_CHANGED = "DEPENDENCIES_CHANGED"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    SOURCE_EVIDENCE_CHANGED = "SOURCE_EVIDENCE_CHANGED"
    AS_OF_CHANGED = "AS_OF_CHANGED"
    SEED_CHANGED = "SEED_CHANGED"
    NO_MATERIAL_CHANGE = "NO_MATERIAL_CHANGE"

class GovernanceState(str, Enum):
    GOVERNED = "GOVERNED"
    REPRODUCIBLE = "REPRODUCIBLE"
    REPRODUCIBILITY_WARNING = "REPRODUCIBILITY_WARNING"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    METHODOLOGY_CHANGED = "METHODOLOGY_CHANGED"
    DATA_CHANGED = "DATA_CHANGED"
    CONCLUSION_CONFLICT = "CONCLUSION_CONFLICT"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"
    INSUFFICIENT_AUDIT_TRAIL = "INSUFFICIENT_AUDIT_TRAIL"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"

class ResearchReproducibilityManifest(BaseModel):
    manifest_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_identity_hash: str
    experiment_id: str = "UNKNOWN"
    meta_analysis_id: str = "UNKNOWN"
    dataset_identity: str = "UNKNOWN"
    dataset_version: str = "UNKNOWN"
    historical_start: Optional[datetime] = None
    historical_end: Optional[datetime] = None
    as_of: datetime
    seed: Optional[int] = None
    strategy_identity: str = "UNKNOWN"
    strategy_version: str = "UNKNOWN"
    methodology_version: str = "UNKNOWN"
    configuration_fingerprint: str = "UNKNOWN"
    parameter_fingerprint: str = "UNKNOWN"
    code_fingerprint: str = "UNKNOWN"
    dependency_fingerprint: str = "UNKNOWN"
    schema_version: str = "UNKNOWN"
    analysis_version: str = "UNKNOWN"
    source_evidence_ids: List[str] = Field(default_factory=list)
    creation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    manifest_version: str = "v1"

class ResearchConclusionRevision(BaseModel):
    revision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conclusion_id: str
    research_identity_hash: str
    previous_revision_id: Optional[str] = None
    current_revision_id: str
    manifest_id: str
    conclusion_state: str
    evidence_state: str
    confidence_state: str
    change_type: str = "NO_CHANGE"
    change_summary: str = ""
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    as_of: datetime
    methodology_version: str = "v1"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ResearchAuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    research_identity_hash: str
    source_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    as_of: datetime
    reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    methodology_version: str = "v1"

class ResearchGovernanceStatus(BaseModel):
    research_identity_hash: str
    overall_status: GovernanceState = GovernanceState.NOT_ASSESSABLE
    completeness: CompletenessState = CompletenessState.NON_REPRODUCIBLE
    regression_detected: bool = False
    revalidation_required: bool = False
    last_audit_event_id: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
