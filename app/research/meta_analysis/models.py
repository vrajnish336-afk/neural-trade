from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
from datetime import datetime
import hashlib

class IndependenceClassification(str, Enum):
    SAME_EXPERIMENT = "SAME_EXPERIMENT"
    SAME_DATASET_REPLAY = "SAME_DATASET_REPLAY"
    SAME_TIME_RANGE_REPLAY = "SAME_TIME_RANGE_REPLAY"
    DIFFERENT_SEED_ONLY = "DIFFERENT_SEED_ONLY"
    OVERLAPPING_DATA = "OVERLAPPING_DATA"
    SHARED_METHODOLOGY = "SHARED_METHODOLOGY"
    PARTIALLY_INDEPENDENT = "PARTIALLY_INDEPENDENT"
    INDEPENDENT_DATA = "INDEPENDENT_DATA"
    INDEPENDENT_EXPERIMENT = "INDEPENDENT_EXPERIMENT"
    UNKNOWN = "UNKNOWN"

class HeterogeneityState(str, Enum):
    LOW_HETEROGENEITY = "LOW_HETEROGENEITY"
    MODERATE_HETEROGENEITY = "MODERATE_HETEROGENEITY"
    HIGH_HETEROGENEITY = "HIGH_HETEROGENEITY"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"

class MultipleTestingState(str, Enum):
    NO_RISK_DETECTED = "NO_RISK_DETECTED"
    MULTIPLE_TESTING_RISK = "MULTIPLE_TESTING_RISK"
    HIGH_EXPERIMENT_REUSE = "HIGH_EXPERIMENT_REUSE"
    REPEATED_DATASET_REPLAY = "REPEATED_DATASET_REPLAY"
    LOW_INDEPENDENCE = "LOW_INDEPENDENCE"
    SELECTION_RISK = "SELECTION_RISK"

class MetaResearchStatus(str, Enum):
    ESTABLISHED_WITHIN_TESTED_SCOPE = "ESTABLISHED_WITHIN_TESTED_SCOPE"
    SUPPORTED_BUT_CONDITIONAL = "SUPPORTED_BUT_CONDITIONAL"
    PROMISING_BUT_FRAGILE = "PROMISING_BUT_FRAGILE"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"
    FALSIFIED_WITHIN_TESTED_SCOPE = "FALSIFIED_WITHIN_TESTED_SCOPE"
    NOT_POOLABLE = "NOT_POOLABLE"

class SelectionBiasState(str, Enum):
    NO_BIAS_DETECTED = "NO_BIAS_DETECTED"
    SELECTION_BIAS_RISK = "SELECTION_BIAS_RISK"

class MetaEvidenceUnit(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_identity_hash: str
    source_type: str
    source_id: str
    dataset_identity: str
    historical_start: Optional[datetime] = None
    historical_end: Optional[datetime] = None
    observed_at: datetime
    as_of: datetime
    seed: Optional[int] = None
    strategy_identity: Optional[str] = None
    portfolio_identity: Optional[str] = None
    regime: Optional[str] = "UNKNOWN"
    timeframe: Optional[str] = "UNKNOWN"
    methodology_version: str = "UNKNOWN"
    sample_size: int = 0
    evidence_strength: str = "UNKNOWN"
    validation_state: str = "UNKNOWN"
    replication_class: str = "UNKNOWN"
    consensus_state: str = "UNKNOWN"
    revalidation_state: str = "UNKNOWN"
    causal_state: str = "UNKNOWN"
    contradiction_state: str = "UNKNOWN"
    result_direction: str = "UNKNOWN" # POSITIVE, NEGATIVE, NULL, INCONCLUSIVE
    lineage_references: List[str] = Field(default_factory=list)

class EvidenceCoverageReport(BaseModel):
    research_identities_count: int = 0
    experiments_count: int = 0
    independent_experiments_count: int = 0
    datasets_count: int = 0
    unseen_data_validations_count: int = 0
    regimes_tested_count: int = 0
    timeframes_tested_count: int = 0
    hypotheses_count: int = 0
    validated_count: int = 0
    rejected_count: int = 0
    conflicted_count: int = 0
    stale_count: int = 0
    requires_revalidation_count: int = 0
    insufficient_sample_count: int = 0

class MetaResearchConclusion(BaseModel):
    conclusion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_identity_hash: str
    statement: str
    evidence_state: MetaResearchStatus
    confidence_state: str
    independent_evidence_count: int
    total_evidence_count: int
    contradiction_count: int
    stale_count: int
    replication_count: int
    generalization_state: str
    causal_state: str
    selection_bias_state: SelectionBiasState
    multiple_testing_state: MultipleTestingState
    limitations: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    as_of: datetime
    methodology_version: str = "meta_v1"
