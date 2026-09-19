import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.learning.evolution_models import ResearchEvolutionProposal, EvolutionProposalState, ResearchAnswer

logger = logging.getLogger(__name__)

EVOLUTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_evolution_proposals (
    proposal_id TEXT PRIMARY KEY,
    baseline_experiment_id TEXT,
    source_lesson_ids TEXT,
    source_gap_types TEXT,
    research_question TEXT,
    rationale TEXT,
    baseline_parameters TEXT,
    proposed_parameters TEXT,
    state TEXT,
    new_experiment_id TEXT,
    comparison_id TEXT,
    final_research_answer TEXT,
    methodology_version TEXT,
    created_at TEXT
);
"""

class EvolutionRepository:
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
                conn.executescript(EVOLUTION_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init research_evolution_proposals schema: {e}")

    def save_proposal(self, p: ResearchEvolutionProposal):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_evolution_proposals
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p.proposal_id, p.baseline_experiment_id, json.dumps(p.source_lesson_ids),
                    json.dumps(p.source_gap_types), p.research_question, p.rationale,
                    json.dumps(p.baseline_parameters), json.dumps(p.proposed_parameters),
                    p.state.value, p.new_experiment_id, p.comparison_id,
                    p.final_research_answer.value, p.methodology_version,
                    p.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save evolution proposal: {e}")
            
    def get_proposals(self) -> List[ResearchEvolutionProposal]:
        if not config.ENABLE_PERSISTENCE: return []
        ps = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_evolution_proposals ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    ps.append(ResearchEvolutionProposal(
                        proposal_id=row[0],
                        baseline_experiment_id=row[1],
                        source_lesson_ids=json.loads(row[2]),
                        source_gap_types=json.loads(row[3]),
                        research_question=row[4],
                        rationale=row[5],
                        baseline_parameters=json.loads(row[6]),
                        proposed_parameters=json.loads(row[7]),
                        state=EvolutionProposalState(row[8]),
                        new_experiment_id=row[9],
                        comparison_id=row[10],
                        final_research_answer=ResearchAnswer(row[11]),
                        methodology_version=row[12],
                        created_at=datetime.fromisoformat(row[13])
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch evolution proposals: {e}")
        return ps

    def get_proposal(self, proposal_id: str) -> Optional[ResearchEvolutionProposal]:
        for p in self.get_proposals():
            if p.proposal_id == proposal_id:
                return p
        return None
