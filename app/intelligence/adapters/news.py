import uuid
import json
from typing import List
from datetime import datetime

from app.news.collector import NewsCollector
from app.intelligence.models import WorldObservation, SourceQuality

class NewsAdapter:
    """Adapts Phase 11 NewsCollector output to WorldObservations."""
    
    def __init__(self):
        self.collector = NewsCollector()
        
    def fetch_observations(self) -> List[WorldObservation]:
        records = self.collector.collect()
        observations = []
        for r in records:
            # We treat external text strictly as UNTRUSTED DATA / REPORTED_CLAIM
            # We enforce SourceQuality based on simplistic heuristic or unknown.
            quality = SourceQuality.MEDIUM
            if "reuters" in r.source_url.lower() or "bloomberg" in r.source_url.lower():
                quality = SourceQuality.HIGH
                
            obs = WorldObservation(
                observation_id=str(uuid.uuid4()),
                source_id=r.id,
                source_type="NEWS",
                publisher=r.source,
                category="General News",
                sentiment_score=None, # Raw news starts with unknown sentiment
                published_at=r.published_timestamp,
                retrieved_at=r.discovered_timestamp,
                content_hash=r.content_hash,
                source_quality=quality,
                evidence_type="REPORTED_CLAIM",
                raw_metadata_json=json.dumps({"title": r.title, "url": r.article_url})
            )
            observations.append(obs)
        return observations
