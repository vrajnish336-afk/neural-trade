from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class CausalEvidenceLevel(str, Enum):
    NO_RELATIONSHIP_EVIDENCE = "NO_RELATIONSHIP_EVIDENCE"
    CORRELATIONAL = "CORRELATIONAL"
    TEMPORAL_ASSOCIATION = "TEMPORAL_ASSOCIATION"
    CONDITIONAL_ASSOCIATION = "CONDITIONAL_ASSOCIATION"
    REPEATED_STRUCTURAL_SUPPORT = "REPEATED_STRUCTURAL_SUPPORT"
    MECHANISTICALLY_PLAUSIBLE = "MECHANISTICALLY_PLAUSIBLE"
    CAUSAL_EVIDENCE_SUPPORTED = "CAUSAL_EVIDENCE_SUPPORTED"

class CausalAssessmentState(str, Enum):
    CAUSAL_EVIDENCE_STRONG = "CAUSAL_EVIDENCE_STRONG"
    CAUSAL_EVIDENCE_MODERATE = "CAUSAL_EVIDENCE_MODERATE"
    CAUSAL_EVIDENCE_WEAK = "CAUSAL_EVIDENCE_WEAK"
    CAUSAL_EVIDENCE_INSUFFICIENT = "CAUSAL_EVIDENCE_INSUFFICIENT"
    CONFLICTED = "CONFLICTED"
    UNRESOLVED = "UNRESOLVED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"
    CAUSAL_IDENTIFICATION_LIMITED = "CAUSAL_IDENTIFICATION_LIMITED"

class ConfoundingRisk(BaseModel):
    risk_id: str
    description: str
    overlapping_variables: List[str]

class AlternativeExplanation(BaseModel):
    explanation_id: str
    description: str
    supported_by_evidence: bool = False

class MechanismCandidate(BaseModel):
    mechanism_id: str
    description: str
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    falsified: bool = False

class CausalAssessment(BaseModel):
    assessment_id: str
    hypothesis_id: str
    research_identity: str
    
    causal_level: CausalEvidenceLevel = CausalEvidenceLevel.NO_RELATIONSHIP_EVIDENCE
    assessment_state: CausalAssessmentState = CausalAssessmentState.NOT_ASSESSABLE
    
    mechanisms: List[MechanismCandidate] = Field(default_factory=list)
    confounders: List[ConfoundingRisk] = Field(default_factory=list)
    alternatives: List[AlternativeExplanation] = Field(default_factory=list)
    
    temporal_ordering_verified: bool = False
    conditional_constraints: List[str] = Field(default_factory=list)
    
    explanation: str = ""
    limitations: str = "Research evidence supports the proposed mechanism under the tested conditions; this does not establish universal causality."
    research_gaps: List[str] = Field(default_factory=list)
    
    methodology_version: str = "causality_v1"
    as_of: datetime
    created_at: datetime
