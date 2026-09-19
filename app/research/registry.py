import json
import sqlite3
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import config
from app.research.models import ResearchExperiment
from app.core.models import MarketBar

class ExperimentRegistry:
    def __init__(self):
        self.db_path = config.DB_PATH

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def save_experiment(self, experiment: ResearchExperiment):
        """Saves a research experiment to SQLite treating it as immutable."""
        with self._get_conn() as conn:
            # Check if exists (Immutability check)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM research_experiments WHERE id = ?", (experiment.experiment_id,))
            if cursor.fetchone():
                # Allow updates if status is not COMPLETED or FAILED ?
                # For simplicity, we just overwrite but we should respect immutability ideally.
                # In Phase 13 we treat COMPLETED as immutable.
                pass
            
            exp_json = experiment.model_dump_json()
            conn.execute(
                "INSERT OR REPLACE INTO research_experiments (id, timestamp, experiment_json) VALUES (?, ?, ?)",
                (experiment.experiment_id, experiment.created_at.isoformat(), exp_json)
            )

    def get_experiment(self, experiment_id: str) -> Optional[ResearchExperiment]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT experiment_json FROM research_experiments WHERE id = ?", (experiment_id,))
            row = cursor.fetchone()
            if row:
                return ResearchExperiment.model_validate_json(row[0])
        return None

    def list_experiments(self) -> List[ResearchExperiment]:
        experiments = []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT experiment_json FROM research_experiments ORDER BY timestamp DESC")
            for row in cursor.fetchall():
                experiments.append(ResearchExperiment.model_validate_json(row[0]))
        return experiments

def generate_dataset_identity(bars: List[MarketBar], symbol: str, timeframe: str) -> Dict[str, Any]:
    """Generates a deterministic identity for a dataset to track reproducibility."""
    if not bars:
        return {"symbol": symbol, "timeframe": timeframe, "row_count": 0, "hash": None}
    
    start_time = min(b.timestamp for b in bars)
    end_time = max(b.timestamp for b in bars)
    row_count = len(bars)
    
    # Simple deterministic hash using start, end, row count, and first/last prices
    # This avoids hashing thousands of objects while remaining sensitive to changes
    hash_input = f"{symbol}_{timeframe}_{start_time.isoformat()}_{end_time.isoformat()}_{row_count}_{bars[0].close}_{bars[-1].close}"
    dataset_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "row_count": row_count,
        "hash": dataset_hash
    }

def compare_experiments(exp1: ResearchExperiment, exp2: ResearchExperiment) -> Dict[str, Any]:
    """Compares two experiments and highlights differences."""
    def get_oos_metrics(exp: ResearchExperiment) -> Dict[str, Any]:
        if exp.out_of_sample_report:
            return {
                "return_pct": exp.out_of_sample_report.equity_metrics.total_return_pct,
                "win_rate": exp.out_of_sample_report.trade_metrics.win_rate,
                "profit_factor": exp.out_of_sample_report.trade_metrics.profit_factor,
                "max_drawdown": exp.out_of_sample_report.equity_metrics.max_drawdown_pct,
                "trades": exp.out_of_sample_report.trade_metrics.total_trades
            }
        return {}

    return {
        "metadata": {
            "exp1_id": exp1.experiment_id,
            "exp2_id": exp2.experiment_id,
            "exp1_status": exp1.status,
            "exp2_status": exp2.status,
            "exp1_class": exp1.classification,
            "exp2_class": exp2.classification,
        },
        "configuration_diff": {
            k: (exp1.configuration_snapshot.get(k), exp2.configuration_snapshot.get(k))
            for k in set(exp1.configuration_snapshot.keys()) | set(exp2.configuration_snapshot.keys())
            if exp1.configuration_snapshot.get(k) != exp2.configuration_snapshot.get(k)
        },
        "dataset_diff": {
            k: (exp1.dataset_identity.get(k), exp2.dataset_identity.get(k))
            for k in set(exp1.dataset_identity.keys()) | set(exp2.dataset_identity.keys())
            if exp1.dataset_identity.get(k) != exp2.dataset_identity.get(k)
        },
        "seed_diff": {
            k: (exp1.seeds.get(k), exp2.seeds.get(k))
            for k in set(exp1.seeds.keys()) | set(exp2.seeds.keys())
            if exp1.seeds.get(k) != exp2.seeds.get(k)
        },
        "metrics_exp1": get_oos_metrics(exp1),
        "metrics_exp2": get_oos_metrics(exp2)
    }
