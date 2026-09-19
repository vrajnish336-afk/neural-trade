import sqlite3
import json
import logging
from typing import List, Optional, Any
from datetime import datetime, timezone

from app.config import config
from app.learning.paper_evolution_models import (
    PostMortemObservation, PaperResearchLesson, EvolutionProposal, LessonState, ProposalStatus
)

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS phase60_lessons (
    lesson_id TEXT PRIMARY KEY,
    source_trade_ids TEXT,
    strategy TEXT,
    regime TEXT,
    observation TEXT,
    sample_count INTEGER,
    wins INTEGER,
    losses INTEGER,
    observed_pnl REAL,
    confidence_status TEXT,
    created_at TEXT,
    data_window_start TEXT,
    data_window_end TEXT
);

CREATE TABLE IF NOT EXISTS phase60_proposals (
    proposal_id TEXT PRIMARY KEY,
    lesson_ids TEXT,
    evidence_ids TEXT,
    affected_strategy TEXT,
    affected_parameter TEXT,
    current_value_json TEXT,
    proposed_value_json TEXT,
    delta_json TEXT,
    reason TEXT,
    evidence_summary TEXT,
    sample_size INTEGER,
    validation_status TEXT,
    expected_research_rationale TEXT,
    created_at TEXT,
    status TEXT
);
"""

class PaperEvolutionRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        if not config.ENABLE_PERSISTENCE: return
        try:
            conn = self._get_conn()
            with conn:
                conn.executescript(SCHEMA)
            conn.close()
        except Exception as e:
            logger.error(f"Failed to init phase 60 schema: {e}")

    def save_lesson(self, lesson: PaperResearchLesson):
        if not config.ENABLE_PERSISTENCE: return
        try:
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO phase60_lessons
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lesson.lesson_id,
                    json.dumps(lesson.source_trade_ids),
                    lesson.strategy,
                    lesson.regime,
                    lesson.observation,
                    lesson.sample_count,
                    lesson.wins,
                    lesson.losses,
                    lesson.observed_pnl,
                    lesson.confidence_status.value,
                    lesson.created_at.isoformat(),
                    lesson.data_window_start.isoformat(),
                    lesson.data_window_end.isoformat()
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save lesson: {e}")

    def get_lessons(self) -> List[PaperResearchLesson]:
        if not config.ENABLE_PERSISTENCE: return []
        lessons = []
        try:
            conn = self._get_conn()
            for row in conn.execute("SELECT * FROM phase60_lessons"):
                lessons.append(PaperResearchLesson(
                    lesson_id=row[0],
                    source_trade_ids=json.loads(row[1]),
                    strategy=row[2],
                    regime=row[3],
                    observation=row[4],
                    sample_count=row[5],
                    wins=row[6],
                    losses=row[7],
                    observed_pnl=row[8],
                    confidence_status=LessonState(row[9]),
                    created_at=datetime.fromisoformat(row[10]),
                    data_window_start=datetime.fromisoformat(row[11]),
                    data_window_end=datetime.fromisoformat(row[12])
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Failed to get lessons: {e}")
        return lessons

    def save_proposal(self, proposal: EvolutionProposal):
        if not config.ENABLE_PERSISTENCE: return
        try:
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO phase60_proposals
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    proposal.proposal_id,
                    json.dumps(proposal.lesson_ids),
                    json.dumps(proposal.evidence_ids),
                    proposal.affected_strategy,
                    proposal.affected_parameter,
                    json.dumps(proposal.current_value),
                    json.dumps(proposal.proposed_value),
                    json.dumps(proposal.delta),
                    proposal.reason,
                    proposal.evidence_summary,
                    proposal.sample_size,
                    proposal.validation_status,
                    proposal.expected_research_rationale,
                    proposal.created_at.isoformat(),
                    proposal.status.value
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save proposal: {e}")

    def get_proposals(self) -> List[EvolutionProposal]:
        if not config.ENABLE_PERSISTENCE: return []
        proposals = []
        try:
            conn = self._get_conn()
            for row in conn.execute("SELECT * FROM phase60_proposals"):
                proposals.append(EvolutionProposal(
                    proposal_id=row[0],
                    lesson_ids=json.loads(row[1]),
                    evidence_ids=json.loads(row[2]),
                    affected_strategy=row[3],
                    affected_parameter=row[4],
                    current_value=json.loads(row[5]),
                    proposed_value=json.loads(row[6]),
                    delta=json.loads(row[7]),
                    reason=row[8],
                    evidence_summary=row[9],
                    sample_size=row[10],
                    validation_status=row[11],
                    expected_research_rationale=row[12],
                    created_at=datetime.fromisoformat(row[13]),
                    status=ProposalStatus(row[14])
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Failed to get proposals: {e}")
        return proposals
