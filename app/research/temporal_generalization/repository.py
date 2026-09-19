import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.temporal_generalization.models import (
    WalkForwardWindow, TemporalGeneralizationAssessment, 
    WalkForwardWindowStatus, TemporalGeneralizationState, WalkForwardType
)

logger = logging.getLogger(__name__)

TEMP_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_temporal_windows (
    window_id TEXT PRIMARY KEY,
    run_id TEXT,
    candidate_id TEXT,
    dataset_identity TEXT,
    train_start TEXT,
    train_end TEXT,
    validation_start TEXT,
    validation_end TEXT,
    forward_start TEXT,
    forward_end TEXT,
    methodology_version TEXT,
    strategy_identity TEXT,
    parameter_identity TEXT,
    seed TEXT,
    status TEXT,
    trade_count INTEGER,
    return_pct REAL,
    max_drawdown_pct REAL,
    profit_factor REAL,
    cost_assumptions TEXT,
    regime_coverage TEXT,
    as_of TEXT,
    created_at TEXT,
    lineage TEXT
);

CREATE TABLE IF NOT EXISTS research_temporal_assessments (
    assessment_id TEXT PRIMARY KEY,
    candidate_id TEXT,
    run_id TEXT,
    window_type TEXT,
    total_windows INTEGER,
    successful_windows INTEGER,
    failed_windows INTEGER,
    zero_trade_windows INTEGER,
    performance_dispersion REAL,
    drawdown_dispersion REAL,
    trade_count_dispersion REAL,
    overall_state TEXT,
    research_gaps TEXT,
    as_of TEXT,
    created_at TEXT
);
"""

class TemporalGeneralizationRepository:
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
                conn.executescript(TEMP_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init temporal schema: {e}")

    def save_window(self, w: WalkForwardWindow):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_temporal_windows
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    w.window_id, w.run_id, w.candidate_id, w.dataset_identity,
                    w.train_start.isoformat(), w.train_end.isoformat(),
                    w.validation_start.isoformat(), w.validation_end.isoformat(),
                    w.forward_start.isoformat(), w.forward_end.isoformat(),
                    w.methodology_version, w.strategy_identity, w.parameter_identity,
                    w.seed, w.status.value, w.trade_count, w.return_pct, w.max_drawdown_pct,
                    w.profit_factor, json.dumps(w.cost_assumptions), json.dumps(w.regime_coverage),
                    w.as_of.isoformat(), w.created_at.isoformat(), w.lineage
                ))
        except Exception as e:
            logger.error(f"Failed to save window {w.window_id}: {e}")

    def save_assessment(self, a: TemporalGeneralizationAssessment):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_temporal_assessments
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    a.assessment_id, a.candidate_id, a.run_id, a.window_type.value,
                    a.total_windows, a.successful_windows, a.failed_windows, a.zero_trade_windows,
                    a.performance_dispersion, a.drawdown_dispersion, a.trade_count_dispersion,
                    a.overall_state.value, json.dumps(a.research_gaps),
                    a.as_of.isoformat(), a.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save assessment {a.assessment_id}: {e}")

    def get_windows_for_run(self, run_id: str) -> List[WalkForwardWindow]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_temporal_windows WHERE run_id = ? ORDER BY train_start ASC", (run_id,))
                for row in cursor.fetchall():
                    res.append(WalkForwardWindow(
                        window_id=row[0], run_id=row[1], candidate_id=row[2], dataset_identity=row[3],
                        train_start=datetime.fromisoformat(row[4]), train_end=datetime.fromisoformat(row[5]),
                        validation_start=datetime.fromisoformat(row[6]), validation_end=datetime.fromisoformat(row[7]),
                        forward_start=datetime.fromisoformat(row[8]), forward_end=datetime.fromisoformat(row[9]),
                        methodology_version=row[10], strategy_identity=row[11], parameter_identity=row[12],
                        seed=row[13], status=WalkForwardWindowStatus(row[14]), trade_count=row[15],
                        return_pct=row[16], max_drawdown_pct=row[17], profit_factor=row[18],
                        cost_assumptions=json.loads(row[19]), regime_coverage=json.loads(row[20]),
                        as_of=datetime.fromisoformat(row[21]), created_at=datetime.fromisoformat(row[22]),
                        lineage=row[23]
                    ))
        except Exception:
            pass
        return res

    def get_assessments_for_candidate(self, candidate_id: str) -> List[TemporalGeneralizationAssessment]:
        if not config.ENABLE_PERSISTENCE: return []
        res = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_temporal_assessments WHERE candidate_id = ? ORDER BY created_at DESC", (candidate_id,))
                for row in cursor.fetchall():
                    res.append(TemporalGeneralizationAssessment(
                        assessment_id=row[0], candidate_id=row[1], run_id=row[2],
                        window_type=WalkForwardType(row[3]), total_windows=row[4],
                        successful_windows=row[5], failed_windows=row[6], zero_trade_windows=row[7],
                        performance_dispersion=row[8], drawdown_dispersion=row[9], trade_count_dispersion=row[10],
                        overall_state=TemporalGeneralizationState(row[11]), research_gaps=json.loads(row[12]),
                        as_of=datetime.fromisoformat(row[13]), created_at=datetime.fromisoformat(row[14])
                    ))
        except Exception:
            pass
        return res
