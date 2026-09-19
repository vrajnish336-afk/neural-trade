from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class ConsensusState(str, Enum):
    CONSENSUS_SUPPORTED = "CONSENSUS_SUPPORTED"
    PARTIAL_CONSENSUS = "PARTIAL_CONSENSUS"
    CONDITIONAL_CONSENSUS = "CONDITIONAL_CONSENSUS"
    CONFLICTED = "CONFLICTED"
    UNRESOLVED = "UNRESOLVED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class ConflictType(str, Enum):
    REGIME_CONFLICT = "REGIME_CONFLICT"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    DATASET_CONFLICT = "DATASET_CONFLICT"
    METHODOLOGY_CONFLICT = "METHODOLOGY_CONFLICT"
    COST_CONFLICT = "COST_CONFLICT"
    SAMPLE_SIZE_CONFLICT = "SAMPLE_SIZE_CONFLICT"
    FALSIFICATION_CONFLICT = "FALSIFICATION_CONFLICT"
    UNKNOWN_CONFLICT = "UNKNOWN_CONFLICT"

class ConflictSeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNRESOLVED = "UNRESOLVED"

class ResolutionState(str, Enum):
    RESOLVED_BY_CONDITION = "RESOLVED_BY_CONDITION"
    RESOLVED_BY_METHODOLOGY = "RESOLVED_BY_METHODOLOGY"
    RESOLVED_BY_DATA_SCOPE = "RESOLVED_BY_DATA_SCOPE"
    RESOLVED_BY_FRESHER_EVIDENCE = "RESOLVED_BY_FRESHER_EVIDENCE"
    RESOLVED_BY_FALSIFICATION = "RESOLVED_BY_FALSIFICATION"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    UNRESOLVED = "UNRESOLVED"

class EvidenceConsensusUnit(BaseModel):
    unit_id: str
    evidence_id: str
    dataset_id: Optional[str] = None
    seed: Optional[str] = None
    regime: Optional[str] = None
    methodology_version: Optional[str] = None
    cost_assumption: Optional[str] = None
    support_or_contradiction: str  # "SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"
    is_independent: bool = True
    decay_state: Optional[str] = None
    created_at: datetime

class ConsensusConflict(BaseModel):
    conflict_type: ConflictType
    severity: ConflictSeverity
    resolution: ResolutionState
    condition: Optional[str] = None
    description: str

class ConsensusAssessment(BaseModel):
    assessment_id: str
    hypothesis_id: str
    research_identity: str
    
    state: ConsensusState
    independent_support_count: int = 0
    independent_contradict_count: int = 0
    
    conditional_conditions: List[str] = Field(default_factory=list)
    conflicts: List[ConsensusConflict] = Field(default_factory=list)
    
    excluded_evidence_count: int = 0
    exclusion_reasons: Dict[str, int] = Field(default_factory=dict)
    
    evidence_health_warning: bool = False
    falsification_triggered: bool = False
    multiple_testing_risk: bool = False
    
    explanation: str = ""
    research_gaps: List[str] = Field(default_factory=list)
    
    methodology_version: str = "consensus_v1"
    as_of: datetime
    created_at: datetime
