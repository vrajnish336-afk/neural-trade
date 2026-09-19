import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.hypothesis_validation.models import HypothesisValidationResult, ValidationState, EvidenceClassification, FalsificationState

logger = logging.getLogger(__name__)

VALIDATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_hypothesis_validations (
    validation_id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    research_identity TEXT,
    status TEXT,
    validation_state TEXT,
    evidence_state TEXT,
    support_score REAL,
    contradiction_score REAL,
    evidence_count INTEGER,
    supporting_evidence_ids TEXT,
    contradicting_evidence_ids TEXT,
    unresolved_evidence_ids TEXT,
    falsification_triggered TEXT,
    falsification_reason TEXT,
    robustness_state TEXT,
    generalization_state TEXT,
    sample_size_state TEXT,
    cost_resilience_state TEXT,
    regime_coverage_state TEXT,
    forward_validation_state TEXT,
    explanation TEXT,
    methodology_version TEXT,
    as_of TEXT,
    created_at TEXT
);
"""

class ValidationRepository:
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
                conn.executescript(VALIDATION_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init validation schema: {e}")

    def save_validation(self, v: HypothesisValidationResult):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_hypothesis_validations
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    v.validation_id, v.hypothesis_id, v.research_identity, v.status.value,
                    v.validation_state.value, v.evidence_state.value, v.support_score,
                    v.contradiction_score, v.evidence_count, json.dumps(v.supporting_evidence_ids),
                    json.dumps(v.contradicting_evidence_ids), json.dumps(v.unresolved_evidence_ids),
                    v.falsification_triggered.value, v.falsification_reason, v.robustness_state,
                    v.generalization_state, v.sample_size_state, v.cost_resilience_state,
                    v.regime_coverage_state, v.forward_validation_state, v.explanation,
                    v.methodology_version, v.as_of.isoformat(), v.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save validation {v.validation_id}: {e}")

    def get_validation(self, validation_id: str) -> Optional[HypothesisValidationResult]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_hypothesis_validations WHERE validation_id = ?", (validation_id,))
                row = cursor.fetchone()
                if row:
                    return HypothesisValidationResult(
                        validation_id=row[0], hypothesis_id=row[1], research_identity=row[2],
                        status=ValidationState(row[3]), validation_state=ValidationState(row[4]),
                        evidence_state=EvidenceClassification(row[5]), support_score=row[6],
                        contradiction_score=row[7], evidence_count=row[8],
                        supporting_evidence_ids=json.loads(row[9]),
                        contradicting_evidence_ids=json.loads(row[10]),
                        unresolved_evidence_ids=json.loads(row[11]),
                        falsification_triggered=FalsificationState(row[12]),
                        falsification_reason=row[13], robustness_state=row[14],
                        generalization_state=row[15], sample_size_state=row[16],
                        cost_resilience_state=row[17], regime_coverage_state=row[18],
                        forward_validation_state=row[19], explanation=row[20],
                        methodology_version=row[21], as_of=datetime.fromisoformat(row[22]),
                        created_at=datetime.fromisoformat(row[23])
                    )
        except Exception as e:
            logger.error(f"Failed to get validation {validation_id}: {e}")
        return None

    def get_validations_for_hypothesis(self, hypothesis_id: str, as_of: Optional[datetime] = None) -> List[HypothesisValidationResult]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_hypothesis_validations WHERE hypothesis_id = ? AND as_of <= ? ORDER BY created_at DESC", (hypothesis_id, as_of.isoformat()))
                else:
                    cursor.execute("SELECT * FROM research_hypothesis_validations WHERE hypothesis_id = ? ORDER BY created_at DESC", (hypothesis_id,))
                for row in cursor.fetchall():
                    res.append(HypothesisValidationResult(
                        validation_id=row[0], hypothesis_id=row[1], research_identity=row[2],
                        status=ValidationState(row[3]), validation_state=ValidationState(row[4]),
                        evidence_state=EvidenceClassification(row[5]), support_score=row[6],
                        contradiction_score=row[7], evidence_count=row[8],
                        supporting_evidence_ids=json.loads(row[9]),
                        contradicting_evidence_ids=json.loads(row[10]),
                        unresolved_evidence_ids=json.loads(row[11]),
                        falsification_triggered=FalsificationState(row[12]),
                        falsification_reason=row[13], robustness_state=row[14],
                        generalization_state=row[15], sample_size_state=row[16],
                        cost_resilience_state=row[17], regime_coverage_state=row[18],
                        forward_validation_state=row[19], explanation=row[20],
                        methodology_version=row[21], as_of=datetime.fromisoformat(row[22]),
                        created_at=datetime.fromisoformat(row[23])
                    ))
        except Exception:
            pass
        return res
