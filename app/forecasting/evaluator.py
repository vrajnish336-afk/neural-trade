import numpy as np
from typing import List
from app.core.models import MarketBar

class ForecastEvaluator:
    """Evaluates forecasts against actual future observations strictly chronologically."""
    
    @staticmethod
    def evaluate(predicted_values: List[float], actual_future: List[MarketBar]) -> dict:
        """
        Returns MAE and Directional Accuracy.
        Assumes length of predicted_values matches len(actual_future) for evaluation slice.
        """
        n = min(len(predicted_values), len(actual_future))
        if n == 0:
            return {"mae": None, "directional_accuracy": None}
            
        preds = np.array(predicted_values[:n])
        actuals = np.array([b.close for b in actual_future[:n]])
        
        mae = float(np.mean(np.abs(preds - actuals)))
        
        # Directional accuracy: (P_t > P_0) == (A_t > A_0)
        # We need the anchor price before the forecast. But we can just use bar to bar direction.
        if n > 1:
            pred_dirs = np.sign(np.diff(preds))
            act_dirs = np.sign(np.diff(actuals))
            # 1 for match, 0 for mismatch
            dir_acc = float(np.mean(pred_dirs == act_dirs))
        else:
            dir_acc = 0.5 # Neutral fallback if only 1 horizon
            
        return {
            "mae": mae,
            "directional_accuracy": dir_acc
        }
