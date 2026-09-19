import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.revalidation.models import (
    RevalidationAssessment, DecayState, RevalidationReason, EvidenceStrengthLevel
)

logger = logging.getLogger(__name__)

REVAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_revalidation_results (
    assessment_id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    validation_id TEXT,
    replication_assessment_id TEXT,
    research_identity TEXT,
    evidence_age_days REAL,
    decay_state TEXT,
    drift_flags TEXT,
    revalidation_reasons TEXT,
    original_evidence_strength TEXT,
    current_evidence_strength TEXT,
    explanation TEXT,
    revalidation_required BOOLEAN,
    methodology_version TEXT,
    as_of TEXT,
    created_at TEXT
);
"""

class RevalidationRepository:
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
                conn.executescript(REVAL_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init revalidation schema: {e}")

    def save_result(self, r: RevalidationAssessment):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_revalidation_results
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.assessment_id, r.hypothesis_id, r.validation_id, r.replication_assessment_id,
                    r.research_identity, r.evidence_age_days, r.decay_state.value,
                    json.dumps(r.drift_flags), json.dumps([rr.value for rr in r.revalidation_reasons]),
                    r.original_evidence_strength.value, r.current_evidence_strength.value,
                    r.explanation, r.revalidation_required, r.methodology_version,
                    r.as_of.isoformat(), r.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save revalidation result {r.assessment_id}: {e}")

    def get_result(self, assessment_id: str) -> Optional[RevalidationAssessment]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_revalidation_results WHERE assessment_id = ?", (assessment_id,))
                row = cursor.fetchone()
                if row:
                    return RevalidationAssessment(
                        assessment_id=row[0], hypothesis_id=row[1], validation_id=row[2],
                        replication_assessment_id=row[3], research_identity=row[4],
                        evidence_age_days=row[5], decay_state=DecayState(row[6]),
                        drift_flags=json.loads(row[7]), 
                        revalidation_reasons=[RevalidationReason(x) for x in json.loads(row[8])],
                        original_evidence_strength=EvidenceStrengthLevel(row[9]),
                        current_evidence_strength=EvidenceStrengthLevel(row[10]),
                        explanation=row[11], revalidation_required=bool(row[12]),
                        methodology_version=row[13],
                        as_of=datetime.fromisoformat(row[14]), created_at=datetime.fromisoformat(row[15])
                    )
        except Exception as e:
            logger.error(f"Failed to get revalidation result {assessment_id}: {e}")
        return None

    def get_results_for_hypothesis(self, hypothesis_id: str, as_of: Optional[datetime] = None) -> List[RevalidationAssessment]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_revalidation_results WHERE hypothesis_id = ? AND as_of <= ? ORDER BY created_at DESC", (hypothesis_id, as_of.isoformat()))
                else:
                    cursor.execute("SELECT * FROM research_revalidation_results WHERE hypothesis_id = ? ORDER BY created_at DESC", (hypothesis_id,))
                for row in cursor.fetchall():
                    res.append(RevalidationAssessment(
                        assessment_id=row[0], hypothesis_id=row[1], validation_id=row[2],
                        replication_assessment_id=row[3], research_identity=row[4],
                        evidence_age_days=row[5], decay_state=DecayState(row[6]),
                        drift_flags=json.loads(row[7]), 
                        revalidation_reasons=[RevalidationReason(x) for x in json.loads(row[8])],
                        original_evidence_strength=EvidenceStrengthLevel(row[9]),
                        current_evidence_strength=EvidenceStrengthLevel(row[10]),
                        explanation=row[11], revalidation_required=bool(row[12]),
                        methodology_version=row[13],
                        as_of=datetime.fromisoformat(row[14]), created_at=datetime.fromisoformat(row[15])
                    ))
        except Exception:
            pass
        return res

    def get_all_results(self, as_of: Optional[datetime] = None) -> List[RevalidationAssessment]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_revalidation_results WHERE as_of <= ? ORDER BY created_at DESC", (as_of.isoformat(),))
                else:
                    cursor.execute("SELECT * FROM research_revalidation_results ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    res.append(RevalidationAssessment(
                        assessment_id=row[0], hypothesis_id=row[1], validation_id=row[2],
                        replication_assessment_id=row[3], research_identity=row[4],
                        evidence_age_days=row[5], decay_state=DecayState(row[6]),
                        drift_flags=json.loads(row[7]), 
                        revalidation_reasons=[RevalidationReason(x) for x in json.loads(row[8])],
                        original_evidence_strength=EvidenceStrengthLevel(row[9]),
                        current_evidence_strength=EvidenceStrengthLevel(row[10]),
                        explanation=row[11], revalidation_required=bool(row[12]),
                        methodology_version=row[13],
                        as_of=datetime.fromisoformat(row[14]), created_at=datetime.fromisoformat(row[15])
                    ))
        except Exception:
            pass
        return res
