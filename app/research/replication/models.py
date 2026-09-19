from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class ReplicationCategory(str, Enum):
    SAME_RUN = "SAME_RUN"
    SAME_DATASET_REPLAY = "SAME_DATASET_REPLAY"
    OVERLAPPING_DATA = "OVERLAPPING_DATA"
    DIFFERENT_SEED_ONLY = "DIFFERENT_SEED_ONLY"
    DIFFERENT_PERIOD = "DIFFERENT_PERIOD"
    DIFFERENT_REGIME = "DIFFERENT_REGIME"
    UNSEEN_DATA = "UNSEEN_DATA"
    COST_STRESS = "COST_STRESS"
    INDEPENDENT_EXPERIMENT = "INDEPENDENT_EXPERIMENT"
    UNKNOWN = "UNKNOWN"

class GeneralizationState(str, Enum):
    GENERALIZES = "GENERALIZES"
    PARTIAL_GENERALIZATION = "PARTIAL_GENERALIZATION"
    NO_GENERALIZATION = "NO_GENERALIZATION"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTED = "CONFLICTED"
    LIMITED_SCOPE = "LIMITED_SCOPE"
    STALE = "STALE"

class EvidenceStrengthLevel(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    FRAGILE = "FRAGILE"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT = "INSUFFICIENT"
    STALE = "STALE"

class ReplicationAssessment(BaseModel):
    category_counts: Dict[str, int] = Field(default_factory=dict)
    total_independent_units: int = 0
    overlapping_units: int = 0
    same_dataset_units: int = 0
    multiple_testing_risk: bool = False
    evidence_nodes_assessed: int = 0

class ResearchReplicationResult(BaseModel):
    assessment_id: str
    hypothesis_id: str
    validation_id: str
    research_identity: str
    
    replication: ReplicationAssessment
    generalization_state: GeneralizationState = GeneralizationState.INSUFFICIENT_EVIDENCE
    evidence_strength: EvidenceStrengthLevel = EvidenceStrengthLevel.INSUFFICIENT
    
    explanation: str = ""
    falsification_respected: bool = True
    insufficient_sample_flag: bool = False
    
    methodology_version: str = "replication_v1"
    as_of: datetime
    created_at: datetime
