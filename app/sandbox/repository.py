import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.sandbox.models import ResearchCodeProposal, ResearchSandboxExperiment, ProposalStatus, ExperimentStatus

logger = logging.getLogger(__name__)

SANDBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_code_proposals (
    proposal_id TEXT PRIMARY KEY,
    research_identity TEXT,
    title TEXT,
    description TEXT,
    code TEXT,
    entrypoint TEXT,
    language TEXT,
    requested_inputs TEXT,
    expected_outputs TEXT,
    dependencies TEXT,
    assumptions TEXT,
    created_at TEXT,
    model TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS research_sandbox_experiments (
    experiment_id TEXT PRIMARY KEY,
    proposal_id TEXT,
    code_hash TEXT,
    dataset_identity TEXT,
    parameters TEXT,
    seed INTEGER,
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    status TEXT,
    backtest_result_json TEXT,
    evidence TEXT,
    limitations TEXT
);
"""

class SandboxRepository:
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
                conn.executescript(SANDBOX_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init sandbox schema: {e}")

    def save_proposal(self, proposal: ResearchCodeProposal):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_code_proposals
                    (proposal_id, research_identity, title, description, code, entrypoint,
                     language, requested_inputs, expected_outputs, dependencies, assumptions,
                     created_at, model, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    proposal.proposal_id, proposal.research_identity, proposal.title,
                    proposal.description, proposal.code, proposal.entrypoint,
                    proposal.language, json.dumps(proposal.requested_inputs),
                    proposal.expected_outputs, json.dumps(proposal.dependencies),
                    json.dumps(proposal.assumptions), proposal.created_at.isoformat(),
                    proposal.model, proposal.status.value
                ))
        except Exception as e:
            logger.error(f"Failed to save proposal: {e}")
            
    def get_proposals(self) -> List[ResearchCodeProposal]:
        if not config.ENABLE_PERSISTENCE: return []
        proposals = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_code_proposals ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    proposals.append(ResearchCodeProposal(
                        proposal_id=row[0],
                        research_identity=row[1],
                        title=row[2],
                        description=row[3],
                        code=row[4],
                        entrypoint=row[5],
                        language=row[6],
                        requested_inputs=json.loads(row[7]),
                        expected_outputs=row[8],
                        dependencies=json.loads(row[9]),
                        assumptions=json.loads(row[10]),
                        created_at=datetime.fromisoformat(row[11]),
                        model=row[12],
                        status=ProposalStatus(row[13])
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch proposals: {e}")
        return proposals
        
    def save_experiment(self, exp: ResearchSandboxExperiment):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_sandbox_experiments
                    (experiment_id, proposal_id, code_hash, dataset_identity, parameters,
                     seed, created_at, started_at, completed_at, status, backtest_result_json,
                     evidence, limitations)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    exp.experiment_id, exp.proposal_id, exp.code_hash, exp.dataset_identity,
                    json.dumps(exp.parameters), exp.seed, exp.created_at.isoformat(),
                    exp.started_at.isoformat() if exp.started_at else None,
                    exp.completed_at.isoformat() if exp.completed_at else None,
                    exp.status.value, exp.backtest_result_json, exp.evidence,
                    json.dumps(exp.limitations)
                ))
        except Exception as e:
            logger.error(f"Failed to save experiment: {e}")
            
    def get_experiment(self, experiment_id: str) -> Optional[ResearchSandboxExperiment]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_sandbox_experiments WHERE experiment_id = ?", (experiment_id,))
                row = cursor.fetchone()
                if row:
                    return ResearchSandboxExperiment(
                        experiment_id=row[0],
                        proposal_id=row[1],
                        code_hash=row[2],
                        dataset_identity=row[3],
                        parameters=json.loads(row[4]),
                        seed=row[5],
                        created_at=datetime.fromisoformat(row[6]),
                        started_at=datetime.fromisoformat(row[7]) if row[7] else None,
                        completed_at=datetime.fromisoformat(row[8]) if row[8] else None,
                        status=ExperimentStatus(row[9]),
                        backtest_result_json=row[10],
                        evidence=row[11],
                        limitations=json.loads(row[12])
                    )
        except Exception as e:
            logger.error(f"Failed to get experiment: {e}")
        return None
