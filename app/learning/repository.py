import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.learning.models import ResearchLesson, ParameterProposal, LessonState, ProposalState

logger = logging.getLogger(__name__)

LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_lessons (
    lesson_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    strategy TEXT,
    regime TEXT,
    timeframe TEXT,
    lesson_statement TEXT,
    evidence_count INTEGER,
    supporting_observation_ids TEXT,
    conflicting_observation_ids TEXT,
    confidence_score REAL,
    state TEXT,
    created_at TEXT,
    last_observed_at TEXT
);

CREATE TABLE IF NOT EXISTS evolution_proposals (
    proposal_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    strategy TEXT,
    baseline_parameters_json TEXT,
    proposed_parameters_json TEXT,
    supporting_lesson_ids TEXT,
    reason TEXT,
    state TEXT,
    validation_run_id TEXT,
    created_at TEXT
);
"""

class LearningRepository:
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
                conn.executescript(LEARNING_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init learning schema: {e}")

    def save_lesson(self, lesson: ResearchLesson):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_lessons 
                    (lesson_id, identity_hash, strategy, regime, timeframe, lesson_statement, 
                     evidence_count, supporting_observation_ids, conflicting_observation_ids, 
                     confidence_score, state, created_at, last_observed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lesson.lesson_id, lesson.identity_hash, lesson.strategy, lesson.regime, 
                    lesson.timeframe, lesson.lesson_statement, lesson.evidence_count,
                    json.dumps(lesson.supporting_observation_ids),
                    json.dumps(lesson.conflicting_observation_ids),
                    lesson.confidence_score, lesson.state.value,
                    lesson.created_at.isoformat(), lesson.last_observed_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save lesson: {e}")

    def get_lessons(self, identity_hash: Optional[str] = None) -> List[ResearchLesson]:
        if not config.ENABLE_PERSISTENCE: return []
        lessons = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if identity_hash:
                    cursor.execute("SELECT * FROM research_lessons WHERE identity_hash = ?", (identity_hash,))
                else:
                    cursor.execute("SELECT * FROM research_lessons")
                    
                for row in cursor.fetchall():
                    lessons.append(ResearchLesson(
                        lesson_id=row[0],
                        identity_hash=row[1],
                        strategy=row[2],
                        regime=row[3],
                        timeframe=row[4],
                        lesson_statement=row[5],
                        evidence_count=row[6],
                        supporting_observation_ids=json.loads(row[7]),
                        conflicting_observation_ids=json.loads(row[8]),
                        confidence_score=row[9],
                        state=LessonState(row[10]),
                        created_at=datetime.fromisoformat(row[11]),
                        last_observed_at=datetime.fromisoformat(row[12])
                    ))
        except Exception as e:
            logger.error(f"Failed to load lessons: {e}")
        return lessons

    def save_proposal(self, proposal: ParameterProposal):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO evolution_proposals
                    (proposal_id, identity_hash, strategy, baseline_parameters_json, 
                     proposed_parameters_json, supporting_lesson_ids, reason, state, 
                     validation_run_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    proposal.proposal_id, proposal.identity_hash, proposal.strategy,
                    proposal.baseline_parameters_json, proposal.proposed_parameters_json,
                    json.dumps(proposal.supporting_lesson_ids), proposal.reason,
                    proposal.state.value, proposal.validation_run_id,
                    proposal.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save proposal: {e}")

    def get_proposals(self, identity_hash: Optional[str] = None) -> List[ParameterProposal]:
        if not config.ENABLE_PERSISTENCE: return []
        proposals = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if identity_hash:
                    cursor.execute("SELECT * FROM evolution_proposals WHERE identity_hash = ?", (identity_hash,))
                else:
                    cursor.execute("SELECT * FROM evolution_proposals")
                
                for row in cursor.fetchall():
                    proposals.append(ParameterProposal(
                        proposal_id=row[0],
                        identity_hash=row[1],
                        strategy=row[2],
                        baseline_parameters_json=row[3],
                        proposed_parameters_json=row[4],
                        supporting_lesson_ids=json.loads(row[5]),
                        reason=row[6],
                        state=ProposalState(row[7]),
                        validation_run_id=row[8],
                        created_at=datetime.fromisoformat(row[9])
                    ))
        except Exception as e:
            logger.error(f"Failed to get proposals: {e}")
        return proposals
