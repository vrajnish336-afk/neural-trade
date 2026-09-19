import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.causal_experiments.models import (
    CausalExperimentDesign, ExperimentApprovalStatus, ExperimentResult, ExperimentResultStatus
)

logger = logging.getLogger(__name__)

EXP_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_causal_experiment_designs (
    experiment_id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    causal_gap_id TEXT,
    research_question TEXT,
    focal_variable TEXT,
    outcome_variable TEXT,
    candidate_mechanism TEXT,
    control_variables TEXT,
    alternative_explanations TEXT,
    required_conditions TEXT,
    excluded_conditions TEXT,
    dataset_identity TEXT,
    historical_start TEXT,
    historical_end TEXT,
    validation_period TEXT,
    methodology_version TEXT,
    random_seed TEXT,
    status TEXT,
    as_of TEXT,
    created_at TEXT,
    lineage TEXT
);

CREATE TABLE IF NOT EXISTS research_causal_experiment_results (
    result_id TEXT PRIMARY KEY,
    experiment_id TEXT,
    hypothesis_id TEXT,
    dataset_identity TEXT,
    methodology_version TEXT,
    control_condition TEXT,
    treatment_condition TEXT,
    observed_outcome TEXT,
    uncertainty REAL,
    sample_size INTEGER,
    temporal_bounds TEXT,
    validation_bounds TEXT,
    evidence_lineage TEXT,
    confounding_status TEXT,
    alternative_explanation_status TEXT,
    result_status TEXT,
    created_at TEXT
);
"""

class CausalExperimentRepository:
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
                conn.executescript(EXP_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init causal experiment schema: {e}")

    def save_design(self, c: CausalExperimentDesign):
        if not config.ENABLE_PERSISTENCE: return
        
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_causal_experiment_designs
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.experiment_id, c.hypothesis_id, c.causal_gap_id, c.research_question,
                    c.focal_variable, c.outcome_variable, c.candidate_mechanism,
                    json.dumps(c.control_variables), json.dumps(c.alternative_explanations),
                    json.dumps(c.required_conditions), json.dumps(c.excluded_conditions),
                    c.dataset_identity, c.historical_start.isoformat(), c.historical_end.isoformat(),
                    json.dumps({k: v.isoformat() for k, v in c.validation_period.items()}) if c.validation_period else None,
                    c.methodology_version, c.random_seed, c.status.value,
                    c.as_of.isoformat(), c.created_at.isoformat(), c.lineage
                ))
        except Exception as e:
            logger.error(f"Failed to save design {c.experiment_id}: {e}")

    def save_result(self, r: ExperimentResult):
        if not config.ENABLE_PERSISTENCE: return
        
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_causal_experiment_results
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.result_id, r.experiment_id, r.hypothesis_id, r.dataset_identity,
                    r.methodology_version, json.dumps(r.control_condition),
                    json.dumps(r.treatment_condition), json.dumps(r.observed_outcome),
                    r.uncertainty, r.sample_size,
                    json.dumps({k: v.isoformat() for k, v in r.temporal_bounds.items()}),
                    json.dumps({k: v.isoformat() for k, v in r.validation_bounds.items()}) if r.validation_bounds else None,
                    r.evidence_lineage, r.confounding_status, r.alternative_explanation_status,
                    r.result_status.value, r.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save result {r.result_id}: {e}")

    def get_designs_for_hypothesis(self, hypothesis_id: str) -> List[CausalExperimentDesign]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_causal_experiment_designs WHERE hypothesis_id = ? ORDER BY created_at DESC", (hypothesis_id,))
                for row in cursor.fetchall():
                    vp = json.loads(row[14]) if row[14] else None
                    if vp:
                        vp = {k: datetime.fromisoformat(v) for k, v in vp.items()}
                    res.append(CausalExperimentDesign(
                        experiment_id=row[0], hypothesis_id=row[1], causal_gap_id=row[2],
                        research_question=row[3], focal_variable=row[4], outcome_variable=row[5],
                        candidate_mechanism=row[6], control_variables=json.loads(row[7]),
                        alternative_explanations=json.loads(row[8]), required_conditions=json.loads(row[9]),
                        excluded_conditions=json.loads(row[10]), dataset_identity=row[11],
                        historical_start=datetime.fromisoformat(row[12]),
                        historical_end=datetime.fromisoformat(row[13]),
                        validation_period=vp, methodology_version=row[15],
                        random_seed=row[16], status=ExperimentApprovalStatus(row[17]),
                        as_of=datetime.fromisoformat(row[18]), created_at=datetime.fromisoformat(row[19]),
                        lineage=row[20]
                    ))
        except Exception:
            pass
        return res

    def get_results_for_hypothesis(self, hypothesis_id: str) -> List[ExperimentResult]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_causal_experiment_results WHERE hypothesis_id = ? ORDER BY created_at DESC", (hypothesis_id,))
                for row in cursor.fetchall():
                    tb = {k: datetime.fromisoformat(v) for k, v in json.loads(row[10]).items()}
                    vb = json.loads(row[11]) if row[11] else None
                    if vb:
                        vb = {k: datetime.fromisoformat(v) for k, v in vb.items()}
                        
                    res.append(ExperimentResult(
                        result_id=row[0], experiment_id=row[1], hypothesis_id=row[2],
                        dataset_identity=row[3], methodology_version=row[4],
                        control_condition=json.loads(row[5]), treatment_condition=json.loads(row[6]),
                        observed_outcome=json.loads(row[7]), uncertainty=row[8], sample_size=row[9],
                        temporal_bounds=tb, validation_bounds=vb, evidence_lineage=row[12],
                        confounding_status=row[13], alternative_explanation_status=row[14],
                        result_status=ExperimentResultStatus(row[15]), created_at=datetime.fromisoformat(row[16])
                    ))
        except Exception:
            pass
        return res
