import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.causality.models import (
    CausalAssessment, CausalEvidenceLevel, CausalAssessmentState, 
    MechanismCandidate, ConfoundingRisk, AlternativeExplanation
)

logger = logging.getLogger(__name__)

CAUSAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_causal_results (
    assessment_id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    research_identity TEXT,
    causal_level TEXT,
    assessment_state TEXT,
    mechanisms TEXT,
    confounders TEXT,
    alternatives TEXT,
    temporal_ordering_verified BOOLEAN,
    conditional_constraints TEXT,
    explanation TEXT,
    limitations TEXT,
    research_gaps TEXT,
    methodology_version TEXT,
    as_of TEXT,
    created_at TEXT
);
"""

class CausalRepository:
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
                conn.executescript(CAUSAL_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init causality schema: {e}")

    def save_result(self, c: CausalAssessment):
        if not config.ENABLE_PERSISTENCE: return
        
        mech_json = [m.model_dump() for m in c.mechanisms]
        conf_json = [cf.model_dump() for cf in c.confounders]
        alt_json = [a.model_dump() for a in c.alternatives]
            
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_causal_results
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.assessment_id, c.hypothesis_id, c.research_identity, c.causal_level.value,
                    c.assessment_state.value, json.dumps(mech_json), json.dumps(conf_json),
                    json.dumps(alt_json), c.temporal_ordering_verified,
                    json.dumps(c.conditional_constraints), c.explanation, c.limitations,
                    json.dumps(c.research_gaps), c.methodology_version,
                    c.as_of.isoformat(), c.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save causality result {c.assessment_id}: {e}")

    def get_results_for_hypothesis(self, hypothesis_id: str, as_of: Optional[datetime] = None) -> List[CausalAssessment]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_causal_results WHERE hypothesis_id = ? AND as_of <= ? ORDER BY created_at DESC", (hypothesis_id, as_of.isoformat()))
                else:
                    cursor.execute("SELECT * FROM research_causal_results WHERE hypothesis_id = ? ORDER BY created_at DESC", (hypothesis_id,))
                for row in cursor.fetchall():
                    mechs = [MechanismCandidate(**m) for m in json.loads(row[5])]
                    confs = [ConfoundingRisk(**c) for c in json.loads(row[6])]
                    alts = [AlternativeExplanation(**a) for a in json.loads(row[7])]
                    
                    res.append(CausalAssessment(
                        assessment_id=row[0], hypothesis_id=row[1], research_identity=row[2],
                        causal_level=CausalEvidenceLevel(row[3]), assessment_state=CausalAssessmentState(row[4]),
                        mechanisms=mechs, confounders=confs, alternatives=alts,
                        temporal_ordering_verified=bool(row[8]), conditional_constraints=json.loads(row[9]),
                        explanation=row[10], limitations=row[11], research_gaps=json.loads(row[12]),
                        methodology_version=row[13],
                        as_of=datetime.fromisoformat(row[14]), created_at=datetime.fromisoformat(row[15])
                    ))
        except Exception:
            pass
        return res
