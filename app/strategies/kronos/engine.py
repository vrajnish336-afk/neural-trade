import sys
import os
import pandas as pd
import torch
import logging
from typing import List

logger = logging.getLogger(__name__)

# Ensure we can import from the untouched official Kronos repository safely
KRONOS_REPO_PATH = os.getenv("KRONOS_REPO_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "Kronos"))

_KRONOS_AVAILABLE = False
try:
    if KRONOS_REPO_PATH and os.path.isdir(KRONOS_REPO_PATH):
        if KRONOS_REPO_PATH not in sys.path:
            sys.path.append(KRONOS_REPO_PATH)
        from model import Kronos, KronosTokenizer, KronosPredictor
        _KRONOS_AVAILABLE = True
    else:
        logger.warning(f"Kronos repository not found at {KRONOS_REPO_PATH}")
except ImportError as e:
    logger.warning(f"Failed to import Kronos model: {e}")

from app.core.models import MarketBar
from app.strategies.kronos.config import kronos_config

def is_kronos_available() -> bool:
    return _KRONOS_AVAILABLE


class KronosEngineWrapper:
    """
    Wraps the official Kronos model to provide a clean interface
    for Neural Trade while keeping the original source untouched.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KronosEngineWrapper, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
        
    def _initialize(self):
        if not _KRONOS_AVAILABLE:
            raise RuntimeError("Kronos engine is unavailable because the external repository is missing or cannot be imported.")
            
        self.device = kronos_config.device
        self.lookback = kronos_config.lookback
        
        self.tokenizer = KronosTokenizer.from_pretrained(kronos_config.tokenizer_name)
        self.model = Kronos.from_pretrained(kronos_config.model_name)
        self.model = self.model.to(self.device)
        
        self.predictor = KronosPredictor(
            self.model,
            self.tokenizer,
            max_context=self.lookback
        )
        
    def predict(self, historical_bars: List[MarketBar], pred_len: int = 1) -> float:
        """
        Generates a prediction from historical MarketBars.
        Returns the expected percentage return for the predicted close.
        """
        if len(historical_bars) < self.lookback:
            return 0.0 # Insufficient data
            
        # Format for Kronos
        df = pd.DataFrame([{
            "timestamp": b.timestamp,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "amount": 0.0 # Neural Trade might not supply 'amount', but Kronos expects it
        } for b in historical_bars[-self.lookback:]])
        
        x_input = df[["open", "high", "low", "close", "volume", "amount"]]
        x_timestamp = pd.Series(df["timestamp"].values)
        
        last_time = x_timestamp.iloc[-1]
        # Generate dummy future timestamps for prediction alignment
        # The exact freq matters less for a single candle horizon than getting a prediction out.
        future_timestamps = pd.date_range(start=last_time + pd.Timedelta(minutes=5), periods=pred_len, freq="5min")
        y_timestamp = pd.Series(future_timestamps)
        
        current_close = float(df.iloc[-1]["close"])
        
        pred_df = self.predictor.predict(
            df=x_input,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_len,
            T=1.0,
            top_p=0.9,
            sample_count=1
        )
        
        predicted_close = float(pred_df["close"].iloc[-1])
        predicted_return = ((predicted_close - current_close) / current_close) * 100.0
        
        return predicted_return
