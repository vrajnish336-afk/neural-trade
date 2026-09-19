from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
from datetime import datetime

class ReproductionStatus(str, Enum):
    REPRODUCED_EXACTLY = "REPRODUCED_EXACTLY"
    REPRODUCED_WITHIN_TOLERANCE = "REPRODUCED_WITHIN_TOLERANCE"
    REPRODUCTION_MATCHED_STRUCTURALLY = "REPRODUCTION_MATCHED_STRUCTURALLY"
    REPRODUCTION_DIFFERED = "REPRODUCTION_DIFFERED"
    REPRODUCTION_FAILED = "REPRODUCTION_FAILED"
    INSUFFICIENT_REPRODUCTION_DATA = "INSUFFICIENT_REPRODUCTION_DATA"
    REPRODUCTION_UNSUPPORTED = "REPRODUCTION_UNSUPPORTED"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    REPRODUCED_UNDER_CHANGED_ENVIRONMENT = "REPRODUCED_UNDER_CHANGED_ENVIRONMENT"
    REPRODUCTION_BOUNDED = "REPRODUCTION_BOUNDED"

class DiscrepancyCategory(str, Enum):
    NO_DIFFERENCE = "NO_DIFFERENCE"
    NUMERICAL_DRIFT = "NUMERICAL_DRIFT"
    TRADE_SEQUENCE_DIFFERENCE = "TRADE_SEQUENCE_DIFFERENCE"
    DATA_DIFFERENCE = "DATA_DIFFERENCE"
    CONFIGURATION_DIFFERENCE = "CONFIGURATION_DIFFERENCE"
    PARAMETER_DIFFERENCE = "PARAMETER_DIFFERENCE"
    METHODOLOGY_DIFFERENCE = "METHODOLOGY_DIFFERENCE"
    CODE_DIFFERENCE = "CODE_DIFFERENCE"
    DEPENDENCY_DIFFERENCE = "DEPENDENCY_DIFFERENCE"
    SCHEMA_DIFFERENCE = "SCHEMA_DIFFERENCE"
    SEED_DIFFERENCE = "SEED_DIFFERENCE"
    BOUNDARY_DIFFERENCE = "BOUNDARY_DIFFERENCE"
    MISSING_OUTPUT = "MISSING_OUTPUT"
    UNSUPPORTED_RESEARCH_COMPONENT = "UNSUPPORTED_RESEARCH_COMPONENT"
    UNKNOWN_DISCREPANCY = "UNKNOWN_DISCREPANCY"
    NONDETERMINISTIC_OUTPUT_DETECTED = "NONDETERMINISTIC_OUTPUT_DETECTED"

class ReproductionMode(str, Enum):
    METADATA_ONLY = "METADATA_ONLY"
    LIGHTWEIGHT_DETERMINISM_CHECK = "LIGHTWEIGHT_DETERMINISM_CHECK"
    FULL_RESEARCH_RECONSTRUCTION = "FULL_RESEARCH_RECONSTRUCTION"
    SAFE_RESEARCH_REPLAY = "SAFE_RESEARCH_REPLAY"

class ReproductionConfidence(str, Enum):
    HIGH_REPRODUCIBILITY_CONFIDENCE = "HIGH_REPRODUCIBILITY_CONFIDENCE"
    MODERATE_REPRODUCIBILITY_CONFIDENCE = "MODERATE_REPRODUCIBILITY_CONFIDENCE"
    LOW_REPRODUCIBILITY_CONFIDENCE = "LOW_REPRODUCIBILITY_CONFIDENCE"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"

class ComparisonState(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    MATERIAL_DIFFERENCE = "MATERIAL_DIFFERENCE"
    STRUCTURAL_DIFFERENCE = "STRUCTURAL_DIFFERENCE"
    INCOMPATIBLE_OUTPUT = "INCOMPATIBLE_OUTPUT"
    NOT_COMPARABLE = "NOT_COMPARABLE"

class FrozenResearchSpecification(BaseModel):
    specification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_identity_hash: str
    manifest_id: str
    experiment_id: str = "UNKNOWN"
    dataset_identity: str
    dataset_version: str
    historical_start: Optional[datetime] = None
    historical_end: Optional[datetime] = None
    as_of: datetime
    seed: Optional[int] = None
    strategy_identity: str = "UNKNOWN"
    strategy_version: str = "UNKNOWN"
    parameter_fingerprint: str = "UNKNOWN"
    configuration_fingerprint: str = "UNKNOWN"
    methodology_version: str = "UNKNOWN"
    code_fingerprint: str = "UNKNOWN"
    dependency_fingerprint: str = "UNKNOWN"
    schema_version: str = "UNKNOWN"
    analysis_version: str = "UNKNOWN"
    timeframe: str = "UNKNOWN"
    cost_assumptions: Dict[str, Any] = Field(default_factory=dict)
    execution_assumptions: Dict[str, Any] = Field(default_factory=dict)
    validation_boundaries: Dict[str, Any] = Field(default_factory=dict)
    source_evidence_ids: List[str] = Field(default_factory=list)

class OriginalResearchOutput(BaseModel):
    output_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = "UNKNOWN"
    research_identity_hash: str
    result_fingerprint: str = "UNKNOWN"
    trade_count: Optional[int] = None
    return_pct: Optional[float] = None
    risk_metrics: Dict[str, float] = Field(default_factory=dict)
    drawdown_pct: Optional[float] = None
    validation_state: str = "UNKNOWN"
    evidence_state: str = "UNKNOWN"
    conclusion_state: str = "UNKNOWN"
    methodology_version: str = "UNKNOWN"
    source_ids: List[str] = Field(default_factory=list)
    as_of: datetime

class ReproducedResearchOutput(BaseModel):
    reproduction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    specification_id: str
    execution_timestamp: datetime = Field(default_factory=datetime.utcnow)
    dataset_identity: str
    configuration_fingerprint: str
    output_fingerprint: str = "UNKNOWN"
    trade_count: Optional[int] = None
    return_pct: Optional[float] = None
    risk_metrics: Dict[str, float] = Field(default_factory=dict)
    drawdown_pct: Optional[float] = None
    reproduction_mode: ReproductionMode
    resource_usage: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

class ReproductionDiscrepancy(BaseModel):
    discrepancy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: DiscrepancyCategory
    description: str
    evidence_context: str

class IndependentVerificationResult(BaseModel):
    verification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    manifest_id: str
    reproduction_id: str
    status: ReproductionStatus
    confidence: ReproductionConfidence
    comparison_state: ComparisonState
    discrepancies: List[ReproductionDiscrepancy] = Field(default_factory=list)
    independent_replication_supported: bool = False
    revalidation_required: bool = False
    explanation: str
