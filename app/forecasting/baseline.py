import numpy as np
from typing import List
from app.core.models import MarketBar
from app.forecasting.models import ForecastModel, ForecastResult

class BaselineForecaster(ForecastModel):
    """
    A lightweight, CPU-compatible Exponentially Weighted Moving Average (EWMA) trend forecaster.
    Extrapolates the recent trend into the future.
    """
    
    def __init__(self, alpha: float = 0.2):
        self.alpha = alpha
        
    @property
    def model_name(self) -> str:
        return "Baseline_EWMA_Drift"
        
    def predict(self, history: List[MarketBar], horizon: int) -> ForecastResult:
        if not history:
            raise ValueError("History cannot be empty.")
            
        closes = np.array([b.close for b in history])
        
        # Calculate returns
        returns = np.diff(closes) / closes[:-1]
        
        # EWMA of returns
        if len(returns) > 0:
            weights = (1 - self.alpha) ** np.arange(len(returns))[::-1]
            ewma_return = np.sum(weights * returns) / np.sum(weights)
        else:
            ewma_return = 0.0
            
        # Dampen the drift to avoid unrealistic exponential blowups in long horizons
        dampening = 0.95
        
        predictions = []
        current_price = closes[-1]
        
        # We'll also calculate a naive expanding uncertainty band based on historical volatility
        std_dev = np.std(returns) if len(returns) > 1 else 0.01
        
        lower_bounds = []
        upper_bounds = []
        
        for i in range(horizon):
            drift = ewma_return * (dampening ** i)
            current_price = current_price * (1 + drift)
            predictions.append(float(current_price))
            
            # 95% confidence interval roughly grows with sqrt(time)
            uncertainty = current_price * std_dev * np.sqrt(i + 1) * 1.96
            lower_bounds.append(float(current_price - uncertainty))
            upper_bounds.append(float(current_price + uncertainty))
            
        return ForecastResult(
            predicted_values=predictions,
            prediction_interval_lower=lower_bounds,
            prediction_interval_upper=upper_bounds
        )
