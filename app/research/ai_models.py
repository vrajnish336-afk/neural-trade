from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class EvidenceType(str, Enum):
    VERIFIED_FACT = "VERIFIED_FACT"
    REPORTED_CLAIM = "REPORTED_CLAIM"
    AI_INTERPRETATION = "AI_INTERPRETATION"
    RESEARCH_HYPOTHESIS = "RESEARCH_HYPOTHESIS"
    UNCLASSIFIED = "UNCLASSIFIED"

class AIAnalysisResult(BaseModel):
    analysis_id: str
    article_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    provider: str
    model: str
    schema_version: str = "1.0"
    
    relevance_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_type: EvidenceType
    
    summary: str
    market_relevance: str
    affected_symbols: List[str]
    research_hypothesis: Optional[str] = None
    limitations: List[str] = []
    
    is_fallback: bool = False
    error_message: Optional[str] = None
