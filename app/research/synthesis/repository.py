import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.synthesis.models import KnowledgeSynthesis, ResearchHypothesis, KnowledgeState, HypothesisStatus, HypothesisType, HypothesisQualityProfile

logger = logging.getLogger(__name__)

SYNTHESIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_syntheses (
    synthesis_id TEXT PRIMARY KEY,
    research_identity TEXT,
    topic TEXT,
    known_findings TEXT,
    supporting_evidence TEXT,
    contradictory_evidence TEXT,
    unresolved_conflicts TEXT,
    evidence_gaps TEXT,
    confidence_state TEXT,
    sample_size_state TEXT,
    robustness_state TEXT,
    forward_validation_state TEXT,
    regime_coverage TEXT,
    parameter_stability TEXT,
    cost_resilience TEXT,
    knowledge_age TEXT,
    methodology_version TEXT,
    as_of TEXT,
    source_node_ids TEXT,
    source_edge_ids TEXT
);

CREATE TABLE IF NOT EXISTS research_hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    research_identity TEXT,
    hypothesis_text TEXT,
    hypothesis_type TEXT,
    originating_synthesis_id TEXT,
    originating_gap_ids TEXT,
    supporting_node_ids TEXT,
    contradicting_node_ids TEXT,
    expected_observation TEXT,
    falsification_condition TEXT,
    required_dataset TEXT,
    required_time_boundary TEXT,
    required_regimes TEXT,
    required_validation TEXT,
    required_robustness TEXT,
    quality_profile TEXT,
    methodology_version TEXT,
    generated_at TEXT,
    as_of TEXT,
    status TEXT
);
"""

class SynthesisRepository:
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
                conn.executescript(SYNTHESIS_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init synthesis schema: {e}")

    def save_synthesis(self, s: KnowledgeSynthesis):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_syntheses
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.synthesis_id, s.research_identity, s.topic,
                    json.dumps(s.known_findings), json.dumps(s.supporting_evidence),
                    json.dumps(s.contradictory_evidence), json.dumps(s.unresolved_conflicts),
                    json.dumps(s.evidence_gaps), s.confidence_state.value, s.sample_size_state,
                    s.robustness_state, s.forward_validation_state, s.regime_coverage,
                    s.parameter_stability, s.cost_resilience, s.knowledge_age,
                    s.methodology_version, s.as_of.isoformat(),
                    json.dumps(s.source_node_ids), json.dumps(s.source_edge_ids)
                ))
        except Exception as e:
            logger.error(f"Failed to save synthesis {s.synthesis_id}: {e}")

    def get_synthesis(self, synthesis_id: str) -> Optional[KnowledgeSynthesis]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_syntheses WHERE synthesis_id = ?", (synthesis_id,))
                row = cursor.fetchone()
                if row:
                    return KnowledgeSynthesis(
                        synthesis_id=row[0], research_identity=row[1], topic=row[2],
                        known_findings=json.loads(row[3]), supporting_evidence=json.loads(row[4]),
                        contradictory_evidence=json.loads(row[5]), unresolved_conflicts=json.loads(row[6]),
                        evidence_gaps=json.loads(row[7]), confidence_state=KnowledgeState(row[8]),
                        sample_size_state=row[9], robustness_state=row[10], forward_validation_state=row[11],
                        regime_coverage=row[12], parameter_stability=row[13], cost_resilience=row[14],
                        knowledge_age=row[15], methodology_version=row[16],
                        as_of=datetime.fromisoformat(row[17]),
                        source_node_ids=json.loads(row[18]), source_edge_ids=json.loads(row[19])
                    )
        except Exception as e:
            logger.error(f"Failed to get synthesis {synthesis_id}: {e}")
        return None

    def get_all_syntheses(self, as_of: Optional[datetime] = None) -> List[KnowledgeSynthesis]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_syntheses WHERE as_of <= ? ORDER BY as_of DESC", (as_of.isoformat(),))
                else:
                    cursor.execute("SELECT * FROM research_syntheses ORDER BY as_of DESC")
                for row in cursor.fetchall():
                    res.append(KnowledgeSynthesis(
                        synthesis_id=row[0], research_identity=row[1], topic=row[2],
                        known_findings=json.loads(row[3]), supporting_evidence=json.loads(row[4]),
                        contradictory_evidence=json.loads(row[5]), unresolved_conflicts=json.loads(row[6]),
                        evidence_gaps=json.loads(row[7]), confidence_state=KnowledgeState(row[8]),
                        sample_size_state=row[9], robustness_state=row[10], forward_validation_state=row[11],
                        regime_coverage=row[12], parameter_stability=row[13], cost_resilience=row[14],
                        knowledge_age=row[15], methodology_version=row[16],
                        as_of=datetime.fromisoformat(row[17]),
                        source_node_ids=json.loads(row[18]), source_edge_ids=json.loads(row[19])
                    ))
        except Exception as e:
            logger.error(f"Failed to get all syntheses: {e}")
        return res

    def save_hypothesis(self, h: ResearchHypothesis):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_hypotheses
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    h.hypothesis_id, h.research_identity, h.hypothesis_text, h.hypothesis_type.value,
                    h.originating_synthesis_id, json.dumps(h.originating_gap_ids),
                    json.dumps(h.supporting_node_ids), json.dumps(h.contradicting_node_ids),
                    h.expected_observation, h.falsification_condition, h.required_dataset,
                    h.required_time_boundary, json.dumps(h.required_regimes),
                    json.dumps(h.required_validation), json.dumps(h.required_robustness),
                    h.quality_profile.model_dump_json() if h.quality_profile else None,
                    h.methodology_version, h.generated_at.isoformat(),
                    h.as_of.isoformat(), h.status.value
                ))
        except Exception as e:
            logger.error(f"Failed to save hypothesis {h.hypothesis_id}: {e}")

    def get_hypothesis(self, hypothesis_id: str) -> Optional[ResearchHypothesis]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_hypotheses WHERE hypothesis_id = ?", (hypothesis_id,))
                row = cursor.fetchone()
                if row:
                    quality = None
                    if row[15]:
                        quality = HypothesisQualityProfile.model_validate_json(row[15])
                    return ResearchHypothesis(
                        hypothesis_id=row[0], research_identity=row[1], hypothesis_text=row[2],
                        hypothesis_type=HypothesisType(row[3]), originating_synthesis_id=row[4],
                        originating_gap_ids=json.loads(row[5]), supporting_node_ids=json.loads(row[6]),
                        contradicting_node_ids=json.loads(row[7]), expected_observation=row[8],
                        falsification_condition=row[9], required_dataset=row[10],
                        required_time_boundary=row[11], required_regimes=json.loads(row[12]),
                        required_validation=json.loads(row[13]), required_robustness=json.loads(row[14]),
                        quality_profile=quality, methodology_version=row[16],
                        generated_at=datetime.fromisoformat(row[17]), as_of=datetime.fromisoformat(row[18]),
                        status=HypothesisStatus(row[19])
                    )
        except Exception as e:
            logger.error(f"Failed to get hypothesis {hypothesis_id}: {e}")
        return None

    def get_all_hypotheses(self, as_of: Optional[datetime] = None) -> List[ResearchHypothesis]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_hypotheses WHERE as_of <= ? ORDER BY generated_at DESC", (as_of.isoformat(),))
                else:
                    cursor.execute("SELECT * FROM research_hypotheses ORDER BY generated_at DESC")
                for row in cursor.fetchall():
                    quality = None
                    if row[15]:
                        quality = HypothesisQualityProfile.model_validate_json(row[15])
                    res.append(ResearchHypothesis(
                        hypothesis_id=row[0], research_identity=row[1], hypothesis_text=row[2],
                        hypothesis_type=HypothesisType(row[3]), originating_synthesis_id=row[4],
                        originating_gap_ids=json.loads(row[5]), supporting_node_ids=json.loads(row[6]),
                        contradicting_node_ids=json.loads(row[7]), expected_observation=row[8],
                        falsification_condition=row[9], required_dataset=row[10],
                        required_time_boundary=row[11], required_regimes=json.loads(row[12]),
                        required_validation=json.loads(row[13]), required_robustness=json.loads(row[14]),
                        quality_profile=quality, methodology_version=row[16],
                        generated_at=datetime.fromisoformat(row[17]), as_of=datetime.fromisoformat(row[18]),
                        status=HypothesisStatus(row[19])
                    ))
        except Exception:
            pass
        return res
