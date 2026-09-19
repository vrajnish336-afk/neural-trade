from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import json
import hashlib

class EvolutionProposalState(str, Enum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    EXPERIMENT_CREATED = "EXPERIMENT_CREATED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"

class ResearchAnswer(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    PENDING = "PENDING"

class ResearchEvolutionProposal(BaseModel):
    proposal_id: str
    baseline_experiment_id: str
    
    source_lesson_ids: List[str] = Field(default_factory=list)
    source_gap_types: List[str] = Field(default_factory=list)
    
    research_question: str
    rationale: str
    
    baseline_parameters: Dict[str, Any]
    proposed_parameters: Dict[str, Any]
    
    state: EvolutionProposalState = EvolutionProposalState.DRAFT
    
    new_experiment_id: Optional[str] = None
    comparison_id: Optional[str] = None
    
    final_research_answer: ResearchAnswer = ResearchAnswer.PENDING
    
    methodology_version: str = "v1"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_identity_hash(self) -> str:
        data = f"{self.baseline_experiment_id}|{self.research_question}|{json.dumps(self.proposed_parameters, sort_keys=True)}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
