import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.forecasting.models import ForecastRecord

logger = logging.getLogger(__name__)

FORECAST_SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast_runs (
    forecast_id TEXT PRIMARY KEY,
    dataset_identity TEXT,
    symbol TEXT,
    timeframe TEXT,
    input_start TEXT,
    input_end TEXT,
    forecast_start TEXT,
    forecast_end TEXT,
    model_name TEXT,
    model_version TEXT,
    window_size INTEGER,
    forecast_horizon INTEGER,
    predicted_values_json TEXT,
    interval_lower_json TEXT,
    interval_upper_json TEXT,
    status TEXT,
    mae REAL,
    directional_accuracy REAL,
    created_at TEXT
);
"""

class ForecastRepository:
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
                conn.execute(FORECAST_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init forecast schema: {e}")

    def save_record(self, record: ForecastRecord):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO forecast_runs 
                    (forecast_id, dataset_identity, symbol, timeframe, input_start, input_end, 
                     forecast_start, forecast_end, model_name, model_version, window_size, 
                     forecast_horizon, predicted_values_json, interval_lower_json, interval_upper_json, 
                     status, mae, directional_accuracy, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.forecast_id, record.dataset_identity, record.symbol, record.timeframe,
                    record.input_start.isoformat(), record.input_end.isoformat(),
                    record.forecast_start.isoformat(), record.forecast_end.isoformat(),
                    record.model_name, record.model_version, record.window_size, record.forecast_horizon,
                    record.predicted_values_json, record.interval_lower_json, record.interval_upper_json,
                    record.status, record.mae, record.directional_accuracy, record.created_at.isoformat()
                ))
        except Exception as e:
            logger.error(f"Failed to save forecast: {e}")

    def get_records(self, symbol: Optional[str] = None) -> List[ForecastRecord]:
        if not config.ENABLE_PERSISTENCE: return []
        records = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if symbol:
                    cursor.execute("SELECT * FROM forecast_runs WHERE symbol = ? ORDER BY created_at DESC", (symbol,))
                else:
                    cursor.execute("SELECT * FROM forecast_runs ORDER BY created_at DESC")
                    
                for row in cursor.fetchall():
                    records.append(ForecastRecord(
                        forecast_id=row[0],
                        dataset_identity=row[1],
                        symbol=row[2],
                        timeframe=row[3],
                        input_start=datetime.fromisoformat(row[4]),
                        input_end=datetime.fromisoformat(row[5]),
                        forecast_start=datetime.fromisoformat(row[6]),
                        forecast_end=datetime.fromisoformat(row[7]),
                        model_name=row[8],
                        model_version=row[9],
                        window_size=row[10],
                        forecast_horizon=row[11],
                        predicted_values_json=row[12],
                        interval_lower_json=row[13],
                        interval_upper_json=row[14],
                        status=row[15],
                        mae=row[16],
                        directional_accuracy=row[17],
                        created_at=datetime.fromisoformat(row[18])
                    ))
        except Exception as e:
            logger.error(f"Failed to load forecasts: {e}")
        return records
