from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class KnowledgeState(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EMERGING = "EMERGING"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    SUPPORTED = "SUPPORTED"
    CONFLICTED = "CONFLICTED"
    WEAKENED = "WEAKENED"
    STALE = "STALE"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"

class HypothesisStatus(str, Enum):
    GENERATED = "GENERATED"
    SCREENED = "SCREENED"
    TESTABLE = "TESTABLE"
    NOT_TESTABLE = "NOT_TESTABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    QUEUED = "QUEUED"
    TESTED = "TESTED"
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"

class HypothesisType(str, Enum):
    REGIME_HYPOTHESIS = "REGIME_HYPOTHESIS"
    ROBUSTNESS_HYPOTHESIS = "ROBUSTNESS_HYPOTHESIS"
    PARAMETER_STABILITY_HYPOTHESIS = "PARAMETER_STABILITY_HYPOTHESIS"
    COST_RESILIENCE_HYPOTHESIS = "COST_RESILIENCE_HYPOTHESIS"
    GENERALIZATION_HYPOTHESIS = "GENERALIZATION_HYPOTHESIS"
    FORECASTING_HYPOTHESIS = "FORECASTING_HYPOTHESIS"
    DATA_QUALITY_HYPOTHESIS = "DATA_QUALITY_HYPOTHESIS"
    CONFLICT_RESOLUTION_HYPOTHESIS = "CONFLICT_RESOLUTION_HYPOTHESIS"
    REPLICATION_HYPOTHESIS = "REPLICATION_HYPOTHESIS"

class KnowledgeSynthesis(BaseModel):
    synthesis_id: str
    research_identity: str
    topic: str
    known_findings: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradictory_evidence: List[str] = Field(default_factory=list)
    unresolved_conflicts: List[str] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    confidence_state: KnowledgeState = KnowledgeState.INSUFFICIENT_EVIDENCE
    sample_size_state: str = "UNKNOWN"
    robustness_state: str = "UNKNOWN"
    forward_validation_state: str = "UNKNOWN"
    regime_coverage: str = "UNKNOWN"
    parameter_stability: str = "UNKNOWN"
    cost_resilience: str = "UNKNOWN"
    knowledge_age: str = "CURRENT"
    methodology_version: str = "synthesis_v1"
    as_of: datetime
    source_node_ids: List[str] = Field(default_factory=list)
    source_edge_ids: List[str] = Field(default_factory=list)

class HypothesisQualityProfile(BaseModel):
    evidence_support: float = 0.0
    contradiction_level: float = 0.0
    testability: float = 0.0
    reproducibility: float = 0.0
    novelty: float = 0.0
    uncertainty_reduction: float = 0.0
    data_feasibility: float = 0.0
    falsifiability: float = 0.0
    explanation: str = ""
    heuristic_name: str = "HYPOTHESIS_QUALITY_HEURISTIC"

class ResearchHypothesis(BaseModel):
    hypothesis_id: str
    research_identity: str
    hypothesis_text: str
    hypothesis_type: HypothesisType
    originating_synthesis_id: Optional[str] = None
    originating_gap_ids: List[str] = Field(default_factory=list)
    supporting_node_ids: List[str] = Field(default_factory=list)
    contradicting_node_ids: List[str] = Field(default_factory=list)
    expected_observation: str = ""
    falsification_condition: str = ""
    required_dataset: str = "UNKNOWN"
    required_time_boundary: str = "UNKNOWN"
    required_regimes: List[str] = Field(default_factory=list)
    required_validation: List[str] = Field(default_factory=list)
    required_robustness: List[str] = Field(default_factory=list)
    quality_profile: Optional[HypothesisQualityProfile] = None
    methodology_version: str = "hypothesis_v1"
    generated_at: datetime
    as_of: datetime
    status: HypothesisStatus = HypothesisStatus.GENERATED
