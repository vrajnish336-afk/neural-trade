from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import hashlib
import json

class OpportunityStatus(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    ALREADY_RESEARCHED = "ALREADY_RESEARCHED"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    READY_FOR_RESEARCH = "READY_FOR_RESEARCH"
    COMPLETED = "COMPLETED"

class ResearchIdentity(BaseModel):
    identity_hash: str
    normalized_strategy: str
    normalized_symbols: str
    normalized_text: str

    @classmethod
    def generate(cls, strategy: str, symbols: List[str], text: str) -> "ResearchIdentity":
        """Generates a deterministic SHA-256 identity for a research hypothesis."""
        norm_strategy = str(strategy).strip().lower()
        norm_symbols = ",".join(sorted([str(s).strip().upper() for s in symbols]))
        # Simple text normalization: lowercase, strip, remove extra spaces
        import re
        norm_text = re.sub(r'\s+', ' ', str(text).strip().lower())
        
        raw = f"{norm_strategy}|{norm_symbols}|{norm_text}"
        identity_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        
        return cls(
            identity_hash=identity_hash,
            normalized_strategy=norm_strategy,
            normalized_symbols=norm_symbols,
            normalized_text=norm_text
        )

class ResearchMemoryRecord(BaseModel):
    identity_hash: str
    canonical_hypothesis: str
    affected_symbols: List[str]
    mapped_strategy: str
    first_seen_at: datetime
    last_researched_at: Optional[datetime] = None
    latest_experiment_id: Optional[str] = None
    latest_conclusion: Optional[str] = None

class ResearchOpportunity(BaseModel):
    opportunity_id: str
    source_analysis_id: str
    identity_hash: str
    
    hypothesis_text: str
    affected_symbols: List[str]
    mapped_strategy: str
    
    novelty_score: float = Field(ge=0.0, le=1.0)
    evidence_gap_score: float = Field(ge=0.0, le=1.0)
    data_availability_score: float = Field(ge=0.0, le=1.0)
    duplicate_penalty: float = Field(ge=0.0, le=1.0)
    
    research_priority: float = Field(ge=0.0, le=1.0)
    status: OpportunityStatus
    reason: str
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
