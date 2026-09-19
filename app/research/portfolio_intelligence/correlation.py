import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from app.research.portfolio_intelligence.models import CorrelationResult

class CorrelationEngine:
    """Calculates cross-strategy performance metrics safely without claiming causation."""

    MIN_SAMPLE_SIZE = 30  # Don't report correlation on tiny samples

    @staticmethod
    def calculate_correlation(series_a: pd.Series, series_b: pd.Series) -> CorrelationResult:
        """
        Calculates correlation between two return series.
        Expects aligned Pandas Series indexed by datetime.
        """
        # Ensure we only compare overlapping valid data
        df = pd.concat([series_a, series_b], axis=1).dropna()
        sample_size = len(df)
        
        if sample_size < CorrelationEngine.MIN_SAMPLE_SIZE:
            return CorrelationResult(
                sample_size=sample_size,
                is_statistically_significant=False
            )
            
        pearson = df.iloc[:, 0].corr(df.iloc[:, 1], method='pearson')
        spearman = df.iloc[:, 0].corr(df.iloc[:, 1], method='spearman')
        
        return CorrelationResult(
            pearson_correlation=float(pearson) if not pd.isna(pearson) else None,
            spearman_correlation=float(spearman) if not pd.isna(spearman) else None,
            sample_size=sample_size,
            is_statistically_significant=True # Simplified for research simulation
        )

    @staticmethod
    def calculate_drawdown_overlap(drawdowns_a: pd.Series, drawdowns_b: pd.Series, threshold: float = -0.05) -> float:
        """
        Calculates the percentage of time both strategies are in a drawdown worse than `threshold`
        simultaneously, relative to the total time *either* is in a drawdown worse than `threshold`.
        """
        df = pd.concat([drawdowns_a, drawdowns_b], axis=1).dropna()
        if len(df) == 0:
            return 0.0
            
        a_in_dd = df.iloc[:, 0] <= threshold
        b_in_dd = df.iloc[:, 1] <= threshold
        
        either_in_dd = a_in_dd | b_in_dd
        both_in_dd = a_in_dd & b_in_dd
        
        total_either = either_in_dd.sum()
        if total_either == 0:
            return 0.0
            
        return float(both_in_dd.sum() / total_either)
