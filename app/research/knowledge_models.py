from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
from app.research.decision_models import (
    ResearchDecisionState, ResearchConfidenceState, NextResearchAction, 
    ResearchConclusion, ResearchConflict, ResearchRelationship
)

class KnowledgeChangeType(str, Enum):
    NEW_RESEARCH_STARTED = "NEW_RESEARCH_STARTED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    CONCLUSION_CHANGED = "CONCLUSION_CHANGED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
    GAP_IDENTIFIED = "GAP_IDENTIFIED"
    GAP_RESOLVED = "GAP_RESOLVED"
    NEW_PAPER_OBSERVATION = "NEW_PAPER_OBSERVATION"
    HEALTH_STATE_CHANGED = "HEALTH_STATE_CHANGED"
    DEGRADATION_DETECTED = "DEGRADATION_DETECTED"

class ResearchKnowledgeChange(BaseModel):
    change_id: str
    identity_hash: str
    change_type: KnowledgeChangeType
    
    previous_decision: Optional[ResearchDecisionState] = None
    new_decision: Optional[ResearchDecisionState] = None
    
    previous_confidence: Optional[ResearchConfidenceState] = None
    new_confidence: Optional[ResearchConfidenceState] = None
    
    reason: str
    source_reference_id: Optional[str] = None # e.g. conclusion_id, conflict_id, job_id
    created_at: datetime = Field(default_factory=datetime.utcnow)

class EvidenceGapType(str, Enum):
    INSUFFICIENT_OOS_SAMPLE = "INSUFFICIENT_OOS_SAMPLE"
    MISSING_REGIME_COVERAGE = "MISSING_REGIME_COVERAGE"
    MISSING_SEED_DIVERSITY = "MISSING_SEED_DIVERSITY"
    MISSING_WALK_FORWARD = "MISSING_WALK_FORWARD"
    MISSING_COST_STRESS = "MISSING_COST_STRESS"
    UNRESOLVED_ACCOUNTING_ISSUE = "UNRESOLVED_ACCOUNTING_ISSUE"

class EvidenceGapStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WONT_FIX = "WONT_FIX"

class EvidenceGap(BaseModel):
    gap_id: str
    identity_hash: str
    gap_type: EvidenceGapType
    severity: str # "HIGH", "MEDIUM", "LOW"
    status: EvidenceGapStatus = EvidenceGapStatus.OPEN
    recommended_action: NextResearchAction
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

class ResearchKnowledgeSnapshot(BaseModel):
    """
    On-demand ephemeral aggregation of what we know about an identity.
    Never persisted as a whole document, just constructed by the KnowledgeService.
    """
    identity_hash: str
    canonical_hypothesis: str
    affected_symbols: List[str]
    mapped_strategy: str
    
    # Execution Stats
    total_experiments: int
    total_completed_jobs: int
    
    # Current State
    current_decision_state: ResearchDecisionState
    current_confidence_state: ResearchConfidenceState
    next_research_action: NextResearchAction
    
    latest_conclusion: Optional[ResearchConclusion] = None
    
    # Active Issues
    unresolved_conflicts: List[ResearchConflict] = Field(default_factory=list)
    open_evidence_gaps: List[EvidenceGap] = Field(default_factory=list)
    
    # Lineage / Relationships
    related_identities: List[ResearchRelationship] = Field(default_factory=list)
    
    # Metadata
    first_seen_at: datetime
    last_updated_at: datetime
