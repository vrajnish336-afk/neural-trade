import hashlib
import json
import logging
from typing import List, Optional
from datetime import datetime

from app.intelligence.models import WorldContext, WorldObservation
from app.intelligence.repository import IntelligenceRepository
from app.intelligence.adapters.news import NewsAdapter
from app.intelligence.adapters.sentiment import FearAndGreedAdapter
from app.intelligence.adapters.macro import MacroAdapter, FlowAdapter

logger = logging.getLogger(__name__)

class WorldIntelligenceService:
    """Coordinates fetching and aggregating world context strictly adhering to chronological boundaries."""
    
    def __init__(self):
        self.repo = IntelligenceRepository()
        
    def fetch_and_store_all(self):
        """Fetches from all external adapters and stores immutably."""
        adapters = [
            NewsAdapter(),
            FearAndGreedAdapter(),
            MacroAdapter(),
            FlowAdapter()
        ]
        
        count = 0
        for adapter in adapters:
            try:
                obs_list = adapter.fetch_observations()
                for obs in obs_list:
                    if self.repo.save_observation(obs):
                        count += 1
            except Exception as e:
                logger.warning(f"Adapter failed: {e}")
                
        logger.info(f"Ingested {count} new world observations.")
        
    def aggregate_context(self, as_of: datetime) -> WorldContext:
        """
        Deterministically aggregates observations bounded strictly by `as_of`.
        Future information is excluded.
        """
        observations = self.repo.get_observations(as_of=as_of, limit=500)
        
        fng_obs = [o for o in observations if o.source_type == "FEAR_GREED"]
        latest_fng = fng_obs[0] if fng_obs else None
        
        news_obs = [o for o in observations if o.source_type == "NEWS"]
        high_quality = [o for o in news_obs if o.source_quality.value == "HIGH"]
        
        # Calculate naive sentiment summary if we had sentiment scored news, otherwise use FNG as proxy
        sentiment_summary = latest_fng.sentiment_score if latest_fng else None
        
        references = [o.observation_id for o in observations[:10]] # Top 10 most recent
        
        # Lineage hash
        hash_input = f"{as_of.isoformat()}|{len(observations)}|{latest_fng.content_hash if latest_fng else 'N/A'}"
        lineage_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        fng_class = None
        if latest_fng:
            try:
                meta = json.loads(latest_fng.raw_metadata_json)
                fng_class = meta.get("classification")
            except Exception:
                pass
                
        return WorldContext(
            as_of=as_of,
            sentiment_summary=sentiment_summary,
            macro_summary="NOT_AVAILABLE",
            flow_summary="NOT_AVAILABLE",
            fear_and_greed_value=latest_fng.sentiment_score if latest_fng else None,
            fear_and_greed_classification=fng_class,
            source_count=len(observations),
            high_quality_source_count=len(high_quality),
            evidence_references=references,
            lineage_hash=lineage_hash,
            created_at=datetime.utcnow()
        )
