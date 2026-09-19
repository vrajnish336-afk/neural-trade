from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CopilotRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    as_of: datetime
    context_scope: List[str] = Field(default_factory=list, description="List of domains to fetch context from")
    symbol: Optional[str] = None
    research_identity: Optional[str] = None

class CopilotResponse(BaseModel):
    answer: str
    evidence_references: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    is_fallback: bool = False
    as_of: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
