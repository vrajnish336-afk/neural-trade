from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
from datetime import datetime

from app.research.planner.models import ResearchPriorityBreakdown, ResearchDecisionState

class NoveltyState(str, Enum):
    NOVEL = "NOVEL"
    DUPLICATE = "DUPLICATE"
    RELATED = "RELATED"
    ALREADY_RESOLVED = "ALREADY_RESOLVED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class PortfolioResearchQuestionState(str, Enum):
    DISCOVERED = "DISCOVERED"
    DUPLICATE = "DUPLICATE"
    ALREADY_RESOLVED = "ALREADY_RESOLVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class PortfolioResearchQuestion(BaseModel):
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    source_failure: str
    research_gap: str
    question_text: str
    hypothesis: str = ""
    falsification_condition: str = ""
    
    priority: float = 0.0
    priority_breakdown: ResearchPriorityBreakdown
    
    novelty: NoveltyState = NoveltyState.INSUFFICIENT_DATA
    evidence_gap: str = ""
    uncertainty: str = ""
    conflict: str = ""
    feasibility: str = "UNKNOWN"
    staleness: str = "UNKNOWN"
    sample_size_state: str = "UNKNOWN"
    
    validation_requirements: List[str] = Field(default_factory=list)
    replication_requirements: List[str] = Field(default_factory=list)
    
    as_of: datetime
    methodology_version: str = "v1"
    lineage: List[str] = Field(default_factory=list)
    status: PortfolioResearchQuestionState = PortfolioResearchQuestionState.DISCOVERED
    created_at: datetime = Field(default_factory=datetime.utcnow)
