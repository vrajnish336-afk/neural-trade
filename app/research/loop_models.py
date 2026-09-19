from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.research.ai_models import AIAnalysisResult
from app.research.evidence import EvidenceConclusion

class ResearchRequestStatus(str, Enum):
    PENDING = "PENDING"
    INSUFFICIENT_RESEARCH_SPECIFICATION = "INSUFFICIENT_RESEARCH_SPECIFICATION"
    DATASET_UNAVAILABLE = "DATASET_UNAVAILABLE"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    COMPLETED = "COMPLETED"

class AIResearchRequest(BaseModel):
    request_id: str
    analysis_id: str
    article_id: str
    hypothesis_text: str
    
    # Deterministic mapping fields
    affected_symbols: List[str]
    mapped_strategy: Optional[str] = None
    historical_window_days: int = 90
    dataset_identity: Optional[Dict[str, Any]] = None
    random_seed: int = 42
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: ResearchRequestStatus = ResearchRequestStatus.PENDING
    
    # Results
    experiment_id: Optional[str] = None
    evidence_conclusion: Optional[EvidenceConclusion] = None
    failure_reason: Optional[str] = None
