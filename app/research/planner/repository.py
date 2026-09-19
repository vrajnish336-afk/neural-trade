import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.planner.models import ResearchQuestionCandidate, ResearchDecision, ResearchDecisionState, ResearchAction, ResearchPriorityBreakdown

logger = logging.getLogger(__name__)

PLANNER_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_question_candidates (
    question_id TEXT PRIMARY KEY,
    research_identity TEXT,
    research_question TEXT,
    hypothesis_reference TEXT,
    originating_gap TEXT,
    related_experiments TEXT,
    related_lessons TEXT,
    related_conclusions TEXT,
    evidence_strength REAL,
    evidence_gaps TEXT,
    conflict_count INTEGER,
    sample_size_state TEXT,
    forward_validation_state TEXT,
    robustness_state TEXT,
    regime_coverage TEXT,
    parameter_stability TEXT,
    cost_resilience TEXT,
    novelty REAL,
    expected_information_gain REAL,
    research_value REAL,
    priority_score REAL,
    priority_reason TEXT,
    methodology_version TEXT,
    created_at TEXT,
    as_of TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS research_decisions (
    decision_id TEXT PRIMARY KEY,
    research_question_id TEXT,
    recommended_action TEXT,
    priority REAL,
    priority_breakdown TEXT,
    evidence_summary TEXT,
    evidence_gap_summary TEXT,
    conflict_summary TEXT,
    feasibility TEXT,
    expected_information_value REAL,
    required_experiment_type TEXT,
    validation_requirements TEXT,
    dependencies TEXT,
    rationale TEXT,
    status TEXT,
    created_at TEXT,
    as_of TEXT,
    approval_timestamp TEXT,
    methodology_version TEXT
);
"""

class PlannerRepository:
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
                conn.executescript(PLANNER_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init planner schema: {e}")

    def save_candidate(self, c: ResearchQuestionCandidate):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_question_candidates
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.question_id, c.research_identity, c.research_question, c.hypothesis_reference,
                    c.originating_gap, json.dumps(c.related_experiments), json.dumps(c.related_lessons),
                    json.dumps(c.related_conclusions), c.evidence_strength, json.dumps(c.evidence_gaps),
                    c.conflict_count, c.sample_size_state, c.forward_validation_state, c.robustness_state,
                    c.regime_coverage, c.parameter_stability, c.cost_resilience, c.novelty,
                    c.expected_information_gain, c.research_value, c.priority_score, c.priority_reason,
                    c.methodology_version, c.created_at.isoformat(), c.as_of.isoformat(), c.status.value
                ))
        except Exception as e:
            logger.error(f"Failed to save candidate {c.question_id}: {e}")

    def get_candidate(self, question_id: str) -> Optional[ResearchQuestionCandidate]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_question_candidates WHERE question_id = ?", (question_id,))
                row = cursor.fetchone()
                if row:
                    return ResearchQuestionCandidate(
                        question_id=row[0], research_identity=row[1], research_question=row[2],
                        hypothesis_reference=row[3], originating_gap=row[4],
                        related_experiments=json.loads(row[5]), related_lessons=json.loads(row[6]),
                        related_conclusions=json.loads(row[7]), evidence_strength=row[8],
                        evidence_gaps=json.loads(row[9]), conflict_count=row[10],
                        sample_size_state=row[11], forward_validation_state=row[12],
                        robustness_state=row[13], regime_coverage=row[14], parameter_stability=row[15],
                        cost_resilience=row[16], novelty=row[17], expected_information_gain=row[18],
                        research_value=row[19], priority_score=row[20], priority_reason=row[21],
                        methodology_version=row[22], created_at=datetime.fromisoformat(row[23]),
                        as_of=datetime.fromisoformat(row[24]), status=ResearchDecisionState(row[25])
                    )
        except Exception as e:
            logger.error(f"Failed to get candidate {question_id}: {e}")
        return None

    def save_decision(self, d: ResearchDecision):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_decisions
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d.decision_id, d.research_question_id, d.recommended_action.value,
                    d.priority, d.priority_breakdown.model_dump_json(),
                    d.evidence_summary, d.evidence_gap_summary, d.conflict_summary,
                    d.feasibility, d.expected_information_value, d.required_experiment_type,
                    json.dumps(d.validation_requirements), json.dumps(d.dependencies),
                    d.rationale, d.status.value, d.created_at.isoformat(),
                    d.as_of.isoformat(), d.approval_timestamp.isoformat() if d.approval_timestamp else None,
                    d.methodology_version
                ))
        except Exception as e:
            logger.error(f"Failed to save decision {d.decision_id}: {e}")

    def get_decision(self, decision_id: str) -> Optional[ResearchDecision]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_decisions WHERE decision_id = ?", (decision_id,))
                row = cursor.fetchone()
                if row:
                    return ResearchDecision(
                        decision_id=row[0], research_question_id=row[1],
                        recommended_action=ResearchAction(row[2]), priority=row[3],
                        priority_breakdown=ResearchPriorityBreakdown.model_validate_json(row[4]),
                        evidence_summary=row[5], evidence_gap_summary=row[6],
                        conflict_summary=row[7], feasibility=row[8],
                        expected_information_value=row[9], required_experiment_type=row[10],
                        validation_requirements=json.loads(row[11]), dependencies=json.loads(row[12]),
                        rationale=row[13], status=ResearchDecisionState(row[14]),
                        created_at=datetime.fromisoformat(row[15]), as_of=datetime.fromisoformat(row[16]),
                        approval_timestamp=datetime.fromisoformat(row[17]) if row[17] else None,
                        methodology_version=row[18]
                    )
        except Exception as e:
            logger.error(f"Failed to get decision {decision_id}: {e}")
        return None

    def get_ranked_decisions(self, as_of: Optional[datetime] = None) -> List[ResearchDecision]:
        if not config.ENABLE_PERSISTENCE: return []
        decisions = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_decisions WHERE as_of <= ? ORDER BY priority DESC", (as_of.isoformat(),))
                else:
                    cursor.execute("SELECT * FROM research_decisions ORDER BY priority DESC")
                    
                for row in cursor.fetchall():
                    decisions.append(ResearchDecision(
                        decision_id=row[0], research_question_id=row[1],
                        recommended_action=ResearchAction(row[2]), priority=row[3],
                        priority_breakdown=ResearchPriorityBreakdown.model_validate_json(row[4]),
                        evidence_summary=row[5], evidence_gap_summary=row[6],
                        conflict_summary=row[7], feasibility=row[8],
                        expected_information_value=row[9], required_experiment_type=row[10],
                        validation_requirements=json.loads(row[11]), dependencies=json.loads(row[12]),
                        rationale=row[13], status=ResearchDecisionState(row[14]),
                        created_at=datetime.fromisoformat(row[15]), as_of=datetime.fromisoformat(row[16]),
                        approval_timestamp=datetime.fromisoformat(row[17]) if row[17] else None,
                        methodology_version=row[18]
                    ))
        except Exception as e:
            logger.error(f"Failed to get ranked decisions: {e}")
        return decisions
