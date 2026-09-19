from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
from datetime import datetime
from app.research.governance.models import GovernanceState
from app.research.meta_analysis.models import MetaResearchStatus

class RootCauseCategory(str, Enum):
    NO_ROOT_CAUSE = "NO_ROOT_CAUSE"
    DATASET_CHANGED = "DATASET_CHANGED"
    CONFIGURATION_CHANGED = "CONFIGURATION_CHANGED"
    METHODOLOGY_CHANGED = "METHODOLOGY_CHANGED"
    CODE_CHANGED = "CODE_CHANGED"
    DEPENDENCY_CHANGED = "DEPENDENCY_CHANGED"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    AS_OF_CHANGED = "AS_OF_CHANGED"
    SEED_CHANGED = "SEED_CHANGED"
    NUMERICAL_DRIFT = "NUMERICAL_DRIFT"
    EXPECTED_FLOATING_POINT_DRIFT = "EXPECTED_FLOATING_POINT_DRIFT"
    STRUCTURAL_NONDETERMINISM = "STRUCTURAL_NONDETERMINISM"
    MULTIPLE_CONTRIBUTING_FACTORS = "MULTIPLE_CONTRIBUTING_FACTORS"
    UNRESOLVED_DISCREPANCY = "UNRESOLVED_DISCREPANCY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class RootCauseConfidence(str, Enum):
    CONFIRMED = "CONFIRMED"
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
    POSSIBLE = "POSSIBLE"
    UNRESOLVED = "UNRESOLVED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"

class ImpactLevel(str, Enum):
    NO_MATERIAL_IMPACT = "NO_MATERIAL_IMPACT"
    LOW_IMPACT = "LOW_IMPACT"
    MODERATE_IMPACT = "MODERATE_IMPACT"
    HIGH_IMPACT = "HIGH_IMPACT"
    CRITICAL_IMPACT = "CRITICAL_IMPACT"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"

class RootCauseAttribution(BaseModel):
    cause: RootCauseCategory
    confidence: RootCauseConfidence
    evidence: str
    original_value: str = "UNKNOWN"
    reproduced_value: str = "UNKNOWN"
    isolation_status: str
    explanation: str
    limitations: List[str] = Field(default_factory=list)

class DiscrepancyImpactAssessment(BaseModel):
    overall_level: ImpactLevel
    structural_level: ImpactLevel
    metric_impacts: Dict[str, ImpactLevel] = Field(default_factory=dict)
    research_state_impact: Optional[str] = None
    governance_impact: GovernanceState
    explanation: str
    evidence: str

class DiscrepancyResearchPriority(str, Enum):
    CRITICAL_REVALIDATION = "CRITICAL_REVALIDATION"
    HIGH_PRIORITY_GAP = "HIGH_PRIORITY_GAP"
    STANDARD_REVIEW = "STANDARD_REVIEW"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"

class ReproductionDiscrepancyAnalysis(BaseModel):
    analysis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reproduction_id: str
    manifest_id: str
    status: str
    root_causes: List[RootCauseAttribution] = Field(default_factory=list)
    impact: DiscrepancyImpactAssessment
    research_priority: DiscrepancyResearchPriority
    research_gap_id: Optional[str] = None
    as_of: datetime = Field(default_factory=datetime.utcnow)
    limitations: List[str] = Field(default_factory=list)
