from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum
import hashlib
import json

class SourceQuality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class WorldObservation(BaseModel):
    """Immutable normalized representation of world intelligence (news, macro, flow, sentiment)."""
    observation_id: str
    source_id: str
    source_type: str = Field(..., description="NEWS, MACRO, FEAR_GREED, FLOW")
    publisher: str
    symbol_relevance: str = "UNKNOWN"
    category: str
    
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    published_at: Optional[datetime] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    
    content_hash: str
    source_quality: SourceQuality = SourceQuality.UNKNOWN
    evidence_type: str = "REPORTED_CLAIM" # FACT, REPORTED_CLAIM, AI_INTERPRETATION
    
    raw_metadata_json: str = "{}"
    
    def get_hash(self) -> str:
        data = f"{self.source_id}|{self.publisher}|{self.content_hash}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

class WorldContext(BaseModel):
    """Aggregated snapshot of world intelligence as of a specific time."""
    as_of: datetime
    
    sentiment_summary: Optional[float] = None
    macro_summary: str = "NOT_AVAILABLE"
    flow_summary: str = "NOT_AVAILABLE"
    fear_and_greed_value: Optional[float] = None
    fear_and_greed_classification: Optional[str] = None
    
    source_count: int = 0
    high_quality_source_count: int = 0
    
    evidence_references: List[str] = Field(default_factory=list)
    lineage_hash: str
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
