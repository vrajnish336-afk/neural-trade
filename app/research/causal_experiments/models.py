from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class ExperimentApprovalStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class ExperimentType(str, Enum):
    CONTROLLED_REGIME_COMPARISON = "CONTROLLED_REGIME_COMPARISON"
    COST_ISOLATION_EXPERIMENT = "COST_ISOLATION_EXPERIMENT"
    VOLATILITY_ISOLATION_EXPERIMENT = "VOLATILITY_ISOLATION_EXPERIMENT"
    PARAMETER_HOLDOUT_EXPERIMENT = "PARAMETER_HOLDOUT_EXPERIMENT"
    TIMEFRAME_COMPARISON = "TIMEFRAME_COMPARISON"
    MECHANISM_COMPARISON = "MECHANISM_COMPARISON"
    ALTERNATIVE_EXPLANATION_TEST = "ALTERNATIVE_EXPLANATION_TEST"
    UNSEEN_PERIOD_REPLICATION = "UNSEEN_PERIOD_REPLICATION"
    INDEPENDENT_DATASET_REPLICATION = "INDEPENDENT_DATASET_REPLICATION"

class CausalExperimentDesign(BaseModel):
    experiment_id: str
    hypothesis_id: str
    causal_gap_id: str
    
    research_question: str
    focal_variable: str
    outcome_variable: str
    candidate_mechanism: str
    
    control_variables: Dict[str, str] = Field(default_factory=dict)
    alternative_explanations: List[str] = Field(default_factory=list)
    
    required_conditions: List[str] = Field(default_factory=list)
    excluded_conditions: List[str] = Field(default_factory=list)
    
    dataset_identity: str
    historical_start: datetime
    historical_end: datetime
    validation_period: Optional[Dict[str, datetime]] = None
    
    methodology_version: str = "causal_exp_v1"
    random_seed: Optional[str] = None
    
    status: ExperimentApprovalStatus = ExperimentApprovalStatus.DRAFT
    as_of: datetime
    created_at: datetime
    lineage: str

class ExperimentResultStatus(str, Enum):
    SUPPORTS_MECHANISM = "SUPPORTS_MECHANISM"
    WEAKENS_MECHANISM = "WEAKENS_MECHANISM"
    CONTRADICTS_MECHANISM = "CONTRADICTS_MECHANISM"
    INCONCLUSIVE = "INCONCLUSIVE"
    CONFOUNDING_REMAINS = "CONFOUNDING_REMAINS"
    REQUIRES_REPLICATION = "REQUIRES_REPLICATION"
    CAUSAL_EVIDENCE_INSUFFICIENT = "CAUSAL_EVIDENCE_INSUFFICIENT"
    DATA_NOT_AVAILABLE = "DATA_NOT_AVAILABLE"

class ExperimentResult(BaseModel):
    result_id: str
    experiment_id: str
    hypothesis_id: str
    dataset_identity: str
    methodology_version: str
    
    control_condition: Dict[str, str]
    treatment_condition: Dict[str, str]
    observed_outcome: Dict[str, float]
    
    uncertainty: Optional[float] = None
    sample_size: int
    
    temporal_bounds: Dict[str, datetime]
    validation_bounds: Optional[Dict[str, datetime]] = None
    
    evidence_lineage: str
    confounding_status: str
    alternative_explanation_status: str
    
    result_status: ExperimentResultStatus
    created_at: datetime
