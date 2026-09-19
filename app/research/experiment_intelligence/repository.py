import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.experiment_intelligence.models import ExperimentComparison, ExperimentEvidenceProfile, CompatibilityStatus, EvidenceStrength

logger = logging.getLogger(__name__)

COMPARE_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiment_comparisons (
    comparison_id TEXT PRIMARY KEY,
    timestamp TEXT,
    methodology_version TEXT,
    experiment_a_id TEXT,
    experiment_b_id TEXT,
    compatibility TEXT,
    compatibility_notes TEXT,
    profile_a_json TEXT,
    profile_b_json TEXT,
    robustness_winner TEXT,
    performance_winner TEXT,
    coverage_winner TEXT,
    final_research_assessment TEXT,
    recommendation TEXT,
    conflicts_detected TEXT
);
"""

class ExperimentComparisonRepository:
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
                conn.executescript(COMPARE_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init experiment_comparisons schema: {e}")

    def save_comparison(self, comp: ExperimentComparison):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO experiment_comparisons
                    (comparison_id, timestamp, methodology_version, experiment_a_id, experiment_b_id,
                     compatibility, compatibility_notes, profile_a_json, profile_b_json,
                     robustness_winner, performance_winner, coverage_winner,
                     final_research_assessment, recommendation, conflicts_detected)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    comp.comparison_id, comp.timestamp.isoformat(), comp.methodology_version,
                    comp.experiment_a_id, comp.experiment_b_id, comp.compatibility.value,
                    json.dumps(comp.compatibility_notes), comp.profile_a.model_dump_json(),
                    comp.profile_b.model_dump_json(), comp.robustness_winner, comp.performance_winner,
                    comp.coverage_winner, comp.final_research_assessment.value, comp.recommendation,
                    json.dumps(comp.conflicts_detected)
                ))
        except Exception as e:
            logger.error(f"Failed to save comparison: {e}")
            
    def get_comparisons(self) -> List[ExperimentComparison]:
        if not config.ENABLE_PERSISTENCE: return []
        comps = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM experiment_comparisons ORDER BY timestamp DESC")
                for row in cursor.fetchall():
                    comps.append(ExperimentComparison(
                        comparison_id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        methodology_version=row[2],
                        experiment_a_id=row[3],
                        experiment_b_id=row[4],
                        compatibility=CompatibilityStatus(row[5]),
                        compatibility_notes=json.loads(row[6]),
                        profile_a=ExperimentEvidenceProfile.model_validate_json(row[7]),
                        profile_b=ExperimentEvidenceProfile.model_validate_json(row[8]),
                        robustness_winner=row[9],
                        performance_winner=row[10],
                        coverage_winner=row[11],
                        final_research_assessment=EvidenceStrength(row[12]),
                        recommendation=row[13],
                        conflicts_detected=json.loads(row[14])
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch comparisons: {e}")
        return comps
