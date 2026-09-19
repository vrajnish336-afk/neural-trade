import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.consensus.models import (
    ConsensusAssessment, ConsensusState, ConsensusConflict, ConflictType, 
    ConflictSeverity, ResolutionState
)

logger = logging.getLogger(__name__)

CONSENSUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_consensus_results (
    assessment_id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    research_identity TEXT,
    state TEXT,
    independent_support_count INTEGER,
    independent_contradict_count INTEGER,
    conditional_conditions TEXT,
    conflicts TEXT,
    excluded_evidence_count INTEGER,
    exclusion_reasons TEXT,
    evidence_health_warning BOOLEAN,
    falsification_triggered BOOLEAN,
    multiple_testing_risk BOOLEAN,
    explanation TEXT,
    research_gaps TEXT,
    methodology_version TEXT,
    as_of TEXT,
    created_at TEXT
);
"""

class ConsensusRepository:
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
                conn.executescript(CONSENSUS_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init consensus schema: {e}")

    def save_result(self, c: ConsensusAssessment):
        if not config.ENABLE_PERSISTENCE: return
        
        conflicts_json = []
        for cf in c.conflicts:
            conflicts_json.append({
                "conflict_type": cf.conflict_type.value,
                "severity": cf.severity.value,
                "resolution": cf.resolution.value,
                "condition": cf.condition,
                "description": cf.description
            })
            
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_consensus_results
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.assessment_id, c.hypothesis_id, c.research_identity, c.state.value,
                    c.independent_support_count, c.independent_contradict_count,
                    json.dumps(c.conditional_conditions), json.dumps(conflicts_json),
                    c.excluded_evidence_count, json.dumps(c.exclusion_reasons),
                    c.evidence_health_warning, c.falsification_triggered, c.multiple_testing_risk,
                    c.explanation, json.dumps(c.research_gaps), c.methodology_version,
                    c.as_of.isoformat(), c.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save consensus result {c.assessment_id}: {e}")

    def get_results_for_hypothesis(self, hypothesis_id: str, as_of: Optional[datetime] = None) -> List[ConsensusAssessment]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_consensus_results WHERE hypothesis_id = ? AND as_of <= ? ORDER BY created_at DESC", (hypothesis_id, as_of.isoformat()))
                else:
                    cursor.execute("SELECT * FROM research_consensus_results WHERE hypothesis_id = ? ORDER BY created_at DESC", (hypothesis_id,))
                for row in cursor.fetchall():
                    c_list = []
                    for cf in json.loads(row[7]):
                        c_list.append(ConsensusConflict(
                            conflict_type=ConflictType(cf["conflict_type"]),
                            severity=ConflictSeverity(cf["severity"]),
                            resolution=ResolutionState(cf["resolution"]),
                            condition=cf.get("condition"),
                            description=cf["description"]
                        ))
                    
                    res.append(ConsensusAssessment(
                        assessment_id=row[0], hypothesis_id=row[1], research_identity=row[2],
                        state=ConsensusState(row[3]), independent_support_count=row[4],
                        independent_contradict_count=row[5],
                        conditional_conditions=json.loads(row[6]),
                        conflicts=c_list, excluded_evidence_count=row[8],
                        exclusion_reasons=json.loads(row[9]),
                        evidence_health_warning=bool(row[10]), falsification_triggered=bool(row[11]),
                        multiple_testing_risk=bool(row[12]), explanation=row[13],
                        research_gaps=json.loads(row[14]), methodology_version=row[15],
                        as_of=datetime.fromisoformat(row[16]), created_at=datetime.fromisoformat(row[17])
                    ))
        except Exception:
            pass
        return res
