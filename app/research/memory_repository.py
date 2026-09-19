import sqlite3
import logging
import json
from typing import List, Optional
from datetime import datetime

from app.config import config
from app.research.memory_models import ResearchMemoryRecord, ResearchOpportunity, OpportunityStatus

logger = logging.getLogger(__name__)

class ResearchMemoryRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def save_memory(self, memory: ResearchMemoryRecord) -> bool:
        if not config.ENABLE_PERSISTENCE: return False
        try:
            with self._get_conn() as conn:
                conn.execute(
                    '''INSERT INTO research_memory 
                       (identity_hash, canonical_hypothesis, affected_symbols, mapped_strategy, 
                        first_seen_at, last_researched_at, latest_experiment_id, latest_conclusion)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(identity_hash) DO UPDATE SET
                       last_researched_at=excluded.last_researched_at,
                       latest_experiment_id=excluded.latest_experiment_id,
                       latest_conclusion=excluded.latest_conclusion''',
                    (
                        memory.identity_hash,
                        memory.canonical_hypothesis,
                        json.dumps(memory.affected_symbols),
                        memory.mapped_strategy,
                        memory.first_seen_at.isoformat(),
                        memory.last_researched_at.isoformat() if memory.last_researched_at else None,
                        memory.latest_experiment_id,
                        memory.latest_conclusion
                    )
                )
            return True
        except Exception as e:
            logger.error("Failed to save memory: %s", e)
            return False

    def get_memory(self, identity_hash: str) -> Optional[ResearchMemoryRecord]:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_memory WHERE identity_hash = ?", (identity_hash,))
                row = cursor.fetchone()
                if row:
                    return ResearchMemoryRecord(
                        identity_hash=row[0],
                        canonical_hypothesis=row[1],
                        affected_symbols=json.loads(row[2]),
                        mapped_strategy=row[3],
                        first_seen_at=datetime.fromisoformat(row[4]),
                        last_researched_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        latest_experiment_id=row[6],
                        latest_conclusion=row[7]
                    )
        except Exception as e:
            logger.error("Failed to get memory: %s", e)
        return None

    def save_opportunity(self, opp: ResearchOpportunity) -> bool:
        if not config.ENABLE_PERSISTENCE: return False
        try:
            with self._get_conn() as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO research_opportunities 
                       (opportunity_id, source_analysis_id, identity_hash, hypothesis_text, affected_symbols, 
                        mapped_strategy, novelty_score, evidence_gap_score, data_availability_score, 
                        duplicate_penalty, research_priority, status, reason, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        opp.opportunity_id, opp.source_analysis_id, opp.identity_hash,
                        opp.hypothesis_text, json.dumps(opp.affected_symbols), opp.mapped_strategy,
                        opp.novelty_score, opp.evidence_gap_score, opp.data_availability_score,
                        opp.duplicate_penalty, opp.research_priority, opp.status.value,
                        opp.reason, opp.created_at.isoformat()
                    )
                )
            return True
        except Exception as e:
            logger.error("Failed to save opportunity: %s", e)
            return False

    def get_unresolved_opportunities(self, limit: int = 10) -> List[ResearchOpportunity]:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM research_opportunities WHERE status = 'READY_FOR_RESEARCH' ORDER BY research_priority DESC LIMIT ?", 
                    (limit,)
                )
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    results.append(ResearchOpportunity(
                        opportunity_id=row[0],
                        source_analysis_id=row[1],
                        identity_hash=row[2],
                        hypothesis_text=row[3],
                        affected_symbols=json.loads(row[4]),
                        mapped_strategy=row[5],
                        novelty_score=row[6],
                        evidence_gap_score=row[7],
                        data_availability_score=row[8],
                        duplicate_penalty=row[9],
                        research_priority=row[10],
                        status=OpportunityStatus(row[11]),
                        reason=row[12],
                        created_at=datetime.fromisoformat(row[13])
                    ))
                return results
        except Exception as e:
            logger.error("Failed to fetch opportunities: %s", e)
            return []
