import uuid
import json
import urllib.request
import urllib.error
import logging
from typing import List
from datetime import datetime

from app.intelligence.models import WorldObservation, SourceQuality

logger = logging.getLogger(__name__)

class FearAndGreedAdapter:
    """Fetches Fear & Greed index from alternative.me."""
    
    API_URL = "https://api.alternative.me/fng/"
    TIMEOUT = 5
    
    def fetch_observations(self) -> List[WorldObservation]:
        req = urllib.request.Request(self.API_URL, headers={'User-Agent': 'NeuralTrade/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as response:
                if response.status != 200:
                    logger.warning("Fear & Greed API returned non-200 status.")
                    return []
                    
                content = response.read(10240) # Bound response size for safety
                data = json.loads(content)
                
                if "data" not in data or len(data["data"]) == 0:
                    return []
                    
                latest = data["data"][0]
                value = int(latest["value"])
                classification = latest["value_classification"]
                timestamp_str = latest["timestamp"]
                published_at = datetime.fromtimestamp(int(timestamp_str))
                
                # Normalize 0-100 to -1.0 to 1.0 (where -1 = extreme fear, 1 = extreme greed)
                sentiment_score = (value / 50.0) - 1.0
                
                obs = WorldObservation(
                    observation_id=str(uuid.uuid4()),
                    source_id=f"fng_{timestamp_str}",
                    source_type="FEAR_GREED",
                    publisher="Alternative.me",
                    symbol_relevance="CRYPTO_MACRO",
                    category="Market Sentiment",
                    sentiment_score=sentiment_score,
                    confidence=1.0,
                    published_at=published_at,
                    retrieved_at=datetime.utcnow(),
                    content_hash=f"fng_{value}_{timestamp_str}",
                    source_quality=SourceQuality.MEDIUM,
                    evidence_type="FACT",
                    raw_metadata_json=json.dumps({"raw_value": value, "classification": classification})
                )
                return [obs]
                
        except (urllib.error.URLError, json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to fetch Fear & Greed data safely: {e}")
            # Do NOT fabricate data. Return empty/NOT_AVAILABLE implicitly by returning no observations.
            return []
