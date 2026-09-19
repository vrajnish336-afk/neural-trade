import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.continuous_models import ResearchCycle, ResearchCycleState

logger = logging.getLogger(__name__)

CONTINUOUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_cycles (
    cycle_id TEXT PRIMARY KEY,
    state TEXT,
    methodology_version TEXT,
    generated_proposal_ids TEXT,
    completed_proposal_ids TEXT,
    max_proposals INTEGER,
    failure_reason TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""

class ContinuousRepository:
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
                conn.executescript(CONTINUOUS_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init research_cycles schema: {e}")

    def save_cycle(self, c: ResearchCycle):
        if not config.ENABLE_PERSISTENCE: return
        c.updated_at = datetime.utcnow()
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_cycles
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.cycle_id, c.state.value, c.methodology_version,
                    json.dumps(c.generated_proposal_ids), json.dumps(c.completed_proposal_ids),
                    c.max_proposals, c.failure_reason,
                    c.created_at.isoformat(), c.updated_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save research cycle: {e}")
            
    def get_cycles(self) -> List[ResearchCycle]:
        if not config.ENABLE_PERSISTENCE: return []
        cycles = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_cycles ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    cycles.append(ResearchCycle(
                        cycle_id=row[0],
                        state=ResearchCycleState(row[1]),
                        methodology_version=row[2],
                        generated_proposal_ids=json.loads(row[3]),
                        completed_proposal_ids=json.loads(row[4]),
                        max_proposals=row[5],
                        failure_reason=row[6],
                        created_at=datetime.fromisoformat(row[7]),
                        updated_at=datetime.fromisoformat(row[8])
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch research cycles: {e}")
        return cycles

    def get_cycle(self, cycle_id: str) -> Optional[ResearchCycle]:
        for c in self.get_cycles():
            if c.cycle_id == cycle_id:
                return c
        return None
        
    def get_active_cycle(self) -> Optional[ResearchCycle]:
        for c in self.get_cycles():
            if c.state not in (ResearchCycleState.COMPLETED, ResearchCycleState.FAILED, ResearchCycleState.CANCELLED):
                return c
        return None
