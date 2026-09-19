import logging
import sys
import json
from typing import List
from datetime import timedelta
import pandas as pd
from app.core.models import MarketBar
from app.forecasting.models import ForecastModel, ForecastResult

logger = logging.getLogger(__name__)

class KronosAdapter(ForecastModel):
    """
    Adapter for local Kronos model (D:\\Kronos).
    Implements singleton caching for heavy PyTorch models.
    """
    
    _model_cache = None
    _tokenizer_cache = None
    _predictor_cache = None
    _import_failed = False

    def __init__(self):
        self._available = False
        self._load_kronos()

    @classmethod
    def _load_kronos(cls):
        if cls._import_failed:
            return
            
        if cls._predictor_cache is not None:
            return

        try:
            import torch
            kronos_path = r"D:\Kronos"
            if kronos_path not in sys.path:
                sys.path.append(kronos_path)
            
            from model import Kronos, KronosTokenizer, KronosPredictor
            
            logger.info("Loading Kronos tokenizer...")
            cls._tokenizer_cache = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
            
            logger.info("Loading Kronos model...")
            model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
            
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            model = model.to(device)
            cls._model_cache = model
            
            cls._predictor_cache = KronosPredictor(
                model=model,
                tokenizer=cls._tokenizer_cache,
                max_context=512
            )
            logger.info(f"Kronos successfully loaded onto {device}")
            
        except ImportError as e:
            cls._import_failed = True
            logger.warning(f"Kronos PyTorch import failed: {e}")
        except Exception as e:
            cls._import_failed = True
            logger.warning(f"Kronos initialization failed: {e}")
            
    def is_available(self) -> bool:
        return self._predictor_cache is not None

    @property
    def model_name(self) -> str:
        return "Kronos_Local"

    def predict(self, history: List[MarketBar], horizon: int) -> ForecastResult:
        if not self.is_available():
            raise RuntimeError("Kronos predictor unavailable or failed to load.")
            
        if not history:
            raise ValueError("Empty history provided for forecasting.")
            
        try:
            import torch
            
            # 1. Translate MarketBar to DataFrame
            data = []
            for b in history[-512:]:  # max_context
                data.append({
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "amount": b.volume * b.close,
                    "timestamps": b.timestamp
                })
            df = pd.DataFrame(data)
            df["timestamps"] = pd.to_datetime(df["timestamps"])
            
            x = df[["open", "high", "low", "close", "volume", "amount"]]
            timestamps = pd.Series(df["timestamps"].values)
            
            # 2. Future timestamps
            last_time = timestamps.iloc[-1]
            if len(timestamps) > 1:
                freq = timestamps.iloc[-1] - timestamps.iloc[-2]
            else:
                freq = timedelta(days=1)
                
            future_timestamps = pd.Series([last_time + freq * (i + 1) for i in range(horizon)])
            
            # 3. Predict
            pred = self._predictor_cache.predict(
                df=x,
                x_timestamp=timestamps,
                y_timestamp=future_timestamps,
                pred_len=horizon,
                T=1.0,
                top_p=0.9,
                sample_count=1
            )
            
            # Handle DataFrame (actual Kronos) or tensor (mock) return types
            if hasattr(pred, 'values'):
                # DataFrame: extract close column or first numeric column
                if 'close' in pred.columns:
                    pred_values = pred['close'].tolist()
                else:
                    pred_values = pred.iloc[:, 0].tolist()
            else:
                pred_values = pred.squeeze().tolist()
            if not isinstance(pred_values, list):
                pred_values = [pred_values]
                
            # 4. Cleanup Memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            return ForecastResult(
                predicted_values=pred_values
            )
            
        except Exception as e:
            logger.error(f"Kronos inference failed: {e}")
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise RuntimeError(f"Kronos inference error: {e}")
