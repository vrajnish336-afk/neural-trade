import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.replication.models import (
    ResearchReplicationResult, ReplicationAssessment, GeneralizationState, EvidenceStrengthLevel
)

logger = logging.getLogger(__name__)

REPLICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_replication_results (
    assessment_id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    validation_id TEXT,
    research_identity TEXT,
    replication_json TEXT,
    generalization_state TEXT,
    evidence_strength TEXT,
    explanation TEXT,
    falsification_respected BOOLEAN,
    insufficient_sample_flag BOOLEAN,
    methodology_version TEXT,
    as_of TEXT,
    created_at TEXT
);
"""

class ReplicationRepository:
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
                conn.executescript(REPLICATION_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init replication schema: {e}")

    def save_result(self, r: ResearchReplicationResult):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_replication_results
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.assessment_id, r.hypothesis_id, r.validation_id, r.research_identity,
                    json.dumps(r.replication.model_dump()), r.generalization_state.value,
                    r.evidence_strength.value, r.explanation, r.falsification_respected,
                    r.insufficient_sample_flag, r.methodology_version,
                    r.as_of.isoformat(), r.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save replication result {r.assessment_id}: {e}")

    def get_result(self, assessment_id: str) -> Optional[ResearchReplicationResult]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_replication_results WHERE assessment_id = ?", (assessment_id,))
                row = cursor.fetchone()
                if row:
                    return ResearchReplicationResult(
                        assessment_id=row[0], hypothesis_id=row[1], validation_id=row[2],
                        research_identity=row[3], replication=ReplicationAssessment(**json.loads(row[4])),
                        generalization_state=GeneralizationState(row[5]),
                        evidence_strength=EvidenceStrengthLevel(row[6]),
                        explanation=row[7], falsification_respected=bool(row[8]),
                        insufficient_sample_flag=bool(row[9]), methodology_version=row[10],
                        as_of=datetime.fromisoformat(row[11]), created_at=datetime.fromisoformat(row[12])
                    )
        except Exception as e:
            logger.error(f"Failed to get replication result {assessment_id}: {e}")
        return None

    def get_results_for_hypothesis(self, hypothesis_id: str, as_of: Optional[datetime] = None) -> List[ResearchReplicationResult]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_replication_results WHERE hypothesis_id = ? AND as_of <= ? ORDER BY created_at DESC", (hypothesis_id, as_of.isoformat()))
                else:
                    cursor.execute("SELECT * FROM research_replication_results WHERE hypothesis_id = ? ORDER BY created_at DESC", (hypothesis_id,))
                for row in cursor.fetchall():
                    res.append(ResearchReplicationResult(
                        assessment_id=row[0], hypothesis_id=row[1], validation_id=row[2],
                        research_identity=row[3], replication=ReplicationAssessment(**json.loads(row[4])),
                        generalization_state=GeneralizationState(row[5]),
                        evidence_strength=EvidenceStrengthLevel(row[6]),
                        explanation=row[7], falsification_respected=bool(row[8]),
                        insufficient_sample_flag=bool(row[9]), methodology_version=row[10],
                        as_of=datetime.fromisoformat(row[11]), created_at=datetime.fromisoformat(row[12])
                    ))
        except Exception:
            pass
        return res
