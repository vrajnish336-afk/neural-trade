import sqlite3
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.intelligence.models import WorldObservation, SourceQuality

logger = logging.getLogger(__name__)

INTELLIGENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_observations (
    observation_id TEXT PRIMARY KEY,
    source_id TEXT,
    source_type TEXT,
    publisher TEXT,
    symbol_relevance TEXT,
    category TEXT,
    sentiment_score REAL,
    confidence REAL,
    published_at TEXT,
    retrieved_at TEXT,
    observed_at TEXT,
    content_hash TEXT,
    source_quality TEXT,
    evidence_type TEXT,
    raw_metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_world_obs_pub_time ON world_observations(published_at);
CREATE INDEX IF NOT EXISTS idx_world_obs_hash ON world_observations(content_hash);
"""

class IntelligenceRepository:
    def __init__(self):
        if config.ENABLE_PERSISTENCE:
            self._init_db()

    def _get_conn(self):
        if not config.ENABLE_PERSISTENCE:
            raise RuntimeError("Persistence disabled")
        return sqlite3.connect(config.DB_PATH)

    def _init_db(self):
        try:
            with self._get_conn() as conn:
                conn.executescript(INTELLIGENCE_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init intelligence schema: {e}")

    def save_observation(self, obs: WorldObservation) -> bool:
        if not config.ENABLE_PERSISTENCE: return False
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO world_observations 
                    (observation_id, source_id, source_type, publisher, symbol_relevance, category, 
                     sentiment_score, confidence, published_at, retrieved_at, observed_at, 
                     content_hash, source_quality, evidence_type, raw_metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs.observation_id, obs.source_id, obs.source_type, obs.publisher,
                    obs.symbol_relevance, obs.category, obs.sentiment_score, obs.confidence,
                    obs.published_at.isoformat() if obs.published_at else None,
                    obs.retrieved_at.isoformat(), obs.observed_at.isoformat(),
                    obs.content_hash, obs.source_quality.value, obs.evidence_type, obs.raw_metadata_json
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to save observation: {e}")
            return False

    def get_observations(self, as_of: Optional[datetime] = None, source_type: Optional[str] = None, limit: int = 100) -> List[WorldObservation]:
        if not config.ENABLE_PERSISTENCE: return []
        records = []
        try:
            with self._get_conn() as conn:
                query = "SELECT * FROM world_observations WHERE 1=1"
                params = []
                
                if as_of:
                    # Enforce the strict chronological barrier: 
                    # We can only use observations published at or before `as_of`.
                    # If published_at is NULL, we rely on retrieved_at <= as_of
                    query += " AND (published_at <= ? OR (published_at IS NULL AND retrieved_at <= ?))"
                    iso = as_of.isoformat()
                    params.extend([iso, iso])
                    
                if source_type:
                    query += " AND source_type = ?"
                    params.append(source_type)
                    
                query += f" ORDER BY COALESCE(published_at, retrieved_at) DESC LIMIT {limit}"
                
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                
                for row in cursor.fetchall():
                    pub_time = datetime.fromisoformat(row[8]) if row[8] else None
                    records.append(WorldObservation(
                        observation_id=row[0],
                        source_id=row[1],
                        source_type=row[2],
                        publisher=row[3],
                        symbol_relevance=row[4],
                        category=row[5],
                        sentiment_score=row[6],
                        confidence=row[7],
                        published_at=pub_time,
                        retrieved_at=datetime.fromisoformat(row[9]),
                        observed_at=datetime.fromisoformat(row[10]),
                        content_hash=row[11],
                        source_quality=SourceQuality(row[12]),
                        evidence_type=row[13],
                        raw_metadata_json=row[14]
                    ))
        except Exception as e:
            logger.error(f"Failed to load observations: {e}")
        return records
