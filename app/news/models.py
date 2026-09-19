from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class IngestedNewsRecord(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    source_url: str
    article_url: str
    published_timestamp: Optional[datetime] = None
    discovered_timestamp: datetime
    content_hash: str
    validation_status: str
