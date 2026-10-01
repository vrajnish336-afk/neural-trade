import uuid
import json
import logging
import urllib.request
from typing import List
from datetime import datetime

from app.news.collector import NewsCollector
from app.intelligence.models import WorldObservation, SourceQuality
from app.config import config

logger = logging.getLogger(__name__)

class NewsAdapter:
    """Adapts Phase 11 NewsCollector output to WorldObservations."""
    
    def __init__(self):
        self.collector = NewsCollector()
        
    def _evaluate_credibility(self, title: str, summary: str, source_quality: SourceQuality) -> str:
        """
        Evaluates news credibility via LLM. 
        Returns: 'VERIFIED', 'UNVERIFIED', 'RUMOR', or 'CONFLICTING'.
        Fails closed (returns 'UNVERIFIED') on any error.
        """
        prompt = f"""
You are a NEWS CREDIBILITY ANALYST. You DO NOT trade.
Evaluate the credibility of the following news snippet.
TITLE: {title}
SUMMARY: {summary}
SOURCE QUALITY: {source_quality.value}

You MUST classify this news into EXACTLY ONE of these categories:
- VERIFIED (confirmed by official high-quality sources)
- UNVERIFIED (plausible but lacking strong corroboration)
- RUMOR (speculative, unconfirmed, 'people familiar with the matter')
- CONFLICTING (contradictory reports)

Output ONLY a JSON object:
{{
    "credibility": "VERIFIED" | "UNVERIFIED" | "RUMOR" | "CONFLICTING"
}}
"""
        payload = {
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/generate", 
                data=json.dumps(payload).encode('utf-8'), 
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                result_raw = response.read().decode('utf-8')
                result_json = json.loads(result_raw)
                ai_response_text = result_json.get("response", "{}")
                if ai_response_text.startswith("```json"):
                    ai_response_text = ai_response_text.replace("```json\n", "").replace("```", "").strip()
                parsed = json.loads(ai_response_text)
                credibility = parsed.get("credibility", "UNVERIFIED")
                
                if credibility not in ["VERIFIED", "UNVERIFIED", "RUMOR", "CONFLICTING"]:
                    return "UNVERIFIED"
                    
                # Require corroboration from configured trusted sources
                if credibility == "VERIFIED" and source_quality != SourceQuality.HIGH:
                    # Missing corroboration from trusted source
                    return "UNVERIFIED"
                    
                return credibility
                
        except Exception as e:
            logger.warning(f"Credibility filter failed closed: {e}")
            return "UNVERIFIED"

    def fetch_observations(self) -> List[WorldObservation]:
        records = self.collector.collect()
        observations = []
        for r in records:
            # We treat external text strictly as UNTRUSTED DATA / REPORTED_CLAIM
            # We enforce SourceQuality based on simplistic heuristic or unknown.
            quality = SourceQuality.MEDIUM
            if "reuters" in r.source_url.lower() or "bloomberg" in r.source_url.lower():
                quality = SourceQuality.HIGH
                
            if getattr(config, "NEWS_CREDIBILITY_FILTER_ENABLED", False):
                credibility = self._evaluate_credibility(r.title, r.summary, quality)
                if credibility != "VERIFIED":
                    logger.info(f"Dropping news due to credibility filter: {credibility}")
                    continue
                
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
