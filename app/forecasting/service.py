import uuid
import json
import logging
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from app.core.models import MarketBar
from app.forecasting.models import ForecastModel, ForecastResult, ForecastRecord
from app.forecasting.window_builder import WindowBuilder
from app.forecasting.evaluator import ForecastEvaluator
from app.forecasting.repository import ForecastRepository
from app.forecasting.baseline import BaselineForecaster
from app.forecasting.kronos import KronosAdapter
from app.data.csv_provider import CsvHistoricalDataProvider

logger = logging.getLogger(__name__)

class ForecastingService:
    """Provides a safe, bounded forecasting abstraction strictly for research."""
    
    MAX_WINDOW_SIZE = 1000
    MAX_HORIZON = 100
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = data_dir
        self.repo = ForecastRepository()
        self.baseline = BaselineForecaster()
        self.advanced = KronosAdapter()
        
    def _get_model(self, model_name: str) -> ForecastModel:
        if model_name.lower() == "kronos" and self.advanced.is_available():
            return self.advanced
        return self.baseline
        
    def generate_forecast(self, symbol: str, timeframe: str, window_size: int, horizon: int, model_choice: str = "baseline", evaluation_boundary: Optional[datetime] = None) -> Optional[ForecastRecord]:
        """
        Generates a forecast up to the evaluation_boundary. 
        If evaluation_boundary is None, uses all available historical data (simulating production inference).
        """
        # 1. Resource Guardrails
        if window_size > self.MAX_WINDOW_SIZE:
            logger.warning(f"Validation Error: Window size {window_size} exceeds {self.MAX_WINDOW_SIZE}")
            return None
        if horizon > self.MAX_HORIZON:
            logger.warning(f"Validation Error: Horizon {horizon} exceeds {self.MAX_HORIZON}")
            return None
            
        # 2. Data Loading
        provider = CsvHistoricalDataProvider(self.data_dir)
        bars = provider.get_historical_bars(symbol, timeframe, start_time=datetime(1970, 1, 1, tzinfo=timezone.utc))
        if not bars:
            return None
            
        # Sort strictly
        bars.sort(key=lambda x: x.timestamp)
        
        # Split history vs future for evaluation if boundary exists
        if evaluation_boundary:
            input_bars = [b for b in bars if b.timestamp <= evaluation_boundary]
            future_bars = [b for b in bars if b.timestamp > evaluation_boundary]
        else:
            input_bars = bars
            future_bars = []
            
        # 3. Window Slicing
        try:
            history_window = WindowBuilder.build_input_window(input_bars, window_size)
        except ValueError as e:
            logger.error(f"Window build failed: {e}")
            return None
            
        # 4. Predict
        model = self._get_model(model_choice)
        try:
            result = model.predict(history_window, horizon)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return None
            
        # 5. Evaluate if future data exists
        eval_metrics = {"mae": None, "directional_accuracy": None}
        status = "GENERATED"
        if future_bars:
            eval_metrics = ForecastEvaluator.evaluate(result.predicted_values, future_bars)
            status = "EVALUATED"
            
        # Fake future timestamps for metadata simply using constant offsets
        last_t = history_window[-1].timestamp
        f_start = last_t + timedelta(days=1) if timeframe == "1D" else last_t + timedelta(hours=1)
        f_end = last_t + timedelta(days=horizon) if timeframe == "1D" else last_t + timedelta(hours=horizon)
            
        # 6. Persist
        record = ForecastRecord(
            forecast_id=str(uuid.uuid4()),
            dataset_identity="primary",
            symbol=symbol,
            timeframe=timeframe,
            input_start=history_window[0].timestamp,
            input_end=history_window[-1].timestamp,
            forecast_start=f_start,
            forecast_end=f_end,
            model_name=model.model_name,
            model_version="1.0",
            window_size=window_size,
            forecast_horizon=horizon,
            predicted_values_json=json.dumps(result.predicted_values),
            interval_lower_json=json.dumps(result.prediction_interval_lower) if result.prediction_interval_lower else None,
            interval_upper_json=json.dumps(result.prediction_interval_upper) if result.prediction_interval_upper else None,
            status=status,
            mae=eval_metrics["mae"],
            directional_accuracy=eval_metrics["directional_accuracy"]
        )
        
        self.repo.save_record(record)
        return record
