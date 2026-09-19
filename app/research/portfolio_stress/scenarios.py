import pandas as pd
import numpy as np
from typing import Dict, Any, List

class ScenarioPerturbator:
    
    @staticmethod
    def apply_cost_shock(returns_map: Dict[str, pd.Series], multiplier: float = 2.0) -> Dict[str, pd.Series]:
        """
        Synthetically increases the cost by applying a degradation multiplier to the return series.
        Since we assume standard net returns, a simple multiplier of negative days or an absolute fixed penalty per bar.
        For realistic adversarial backtests, we deduct an extra penalty.
        """
        stressed = {}
        for k, v in returns_map.items():
            # Simply apply an extra friction drag
            # For purely synthetic shock, assume an extra 0.05% loss per trade/bar.
            friction = 0.0005 * multiplier
            s = v.copy()
            # Only apply to active periods (non-zero)
            s = s.apply(lambda x: x - friction if abs(x) > 1e-6 else x)
            stressed[k] = s
        return stressed

    @staticmethod
    def apply_missing_candidate(weights: Dict[str, float], candidate_to_drop: str) -> Dict[str, float]:
        """
        Sets a candidate weight to 0. 
        Note: The remaining weights are NOT automatically normalized back to 1.0.
        This simulates the cash drag of a failed candidate.
        """
        new_weights = dict(weights)
        if candidate_to_drop in new_weights:
            new_weights[candidate_to_drop] = 0.0
        return new_weights

    @staticmethod
    def apply_data_integrity_stress(returns_map: Dict[str, pd.Series]) -> Dict[str, pd.Series]:
        """
        Injects data corruption: NaNs and infs into 5% of the data.
        """
        stressed = {}
        for k, v in returns_map.items():
            s = v.copy()
            n = len(s)
            if n > 0:
                idx_nan = np.random.choice(s.index, size=int(n * 0.05), replace=False)
                s.loc[idx_nan] = np.nan
            stressed[k] = s
        return stressed
