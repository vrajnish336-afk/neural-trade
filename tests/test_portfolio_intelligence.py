import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from app.research.portfolio_intelligence.portfolio import PortfolioComposer
from app.research.portfolio_intelligence.correlation import CorrelationEngine
from app.research.portfolio_intelligence.evaluator import PortfolioEvaluator
from app.research.portfolio_intelligence.models import (
    DiversificationAssessment, PortfolioResearchAssessment
)

def test_weight_validation():
    # Valid
    assert PortfolioComposer.validate_weights({"A": 0.5, "B": 0.5})
    assert PortfolioComposer.validate_weights({"A": 0.33333, "B": 0.33333, "C": 0.33334})
    
    # Invalid
    assert not PortfolioComposer.validate_weights({"A": 1.1}) # Sum > 1
    assert not PortfolioComposer.validate_weights({"A": 0.5}) # Sum < 1
    assert not PortfolioComposer.validate_weights({"A": -0.5, "B": 1.5}) # Negative weight

def test_series_alignment():
    # Create two series that only partially overlap
    dates1 = pd.date_range("2024-01-01", "2024-01-10")
    dates2 = pd.date_range("2024-01-05", "2024-01-15")
    
    s1 = pd.Series(np.random.randn(10), index=dates1)
    s2 = pd.Series(np.random.randn(11), index=dates2)
    
    aligned = PortfolioComposer.align_series({"A": s1, "B": s2})
    
    # Should inner join basically - bounded to common start/end
    assert len(aligned) == 6 # Jan 5 through Jan 10
    assert aligned.index.min() == pd.Timestamp("2024-01-05")
    assert aligned.index.max() == pd.Timestamp("2024-01-10")

def test_correlation_sample_size():
    dates = pd.date_range("2024-01-01", periods=10) # Less than MIN_SAMPLE_SIZE
    s1 = pd.Series(np.random.randn(10), index=dates)
    s2 = pd.Series(np.random.randn(10), index=dates)
    
    res = CorrelationEngine.calculate_correlation(s1, s2)
    assert not res.is_statistically_significant
    assert res.pearson_correlation is None

def test_drawdown_overlap():
    dates = pd.date_range("2024-01-01", periods=100)
    # A is in DD (-0.1) for first 10 days
    dd_a = np.zeros(100)
    dd_a[:10] = -0.1
    # B is in DD (-0.1) for first 5 days
    dd_b = np.zeros(100)
    dd_b[:5] = -0.1
    
    s_a = pd.Series(dd_a, index=dates)
    s_b = pd.Series(dd_b, index=dates)
    
    overlap = CorrelationEngine.calculate_drawdown_overlap(s_a, s_b, threshold=-0.05)
    # total either in dd = 10 (A's 10 days)
    # both in dd = 5 (first 5 days)
    # overlap = 5 / 10 = 0.5
    assert overlap == 0.5

def test_evaluator_strict_as_of():
    dates = pd.date_range("2024-01-01", "2024-12-31", tz="UTC")
    returns = pd.Series(np.random.randn(366), index=dates)
    drawdowns = pd.Series(np.zeros(366), index=dates)
    
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    
    with pytest.raises(ValueError, match="Future data leak detected"):
        PortfolioEvaluator.evaluate(
            candidate_ids=["A"],
            weights={"A": 1.0},
            dataset_identity="test",
            returns_map={"A": returns},
            drawdowns_map={"A": drawdowns},
            cost_model={},
            risk_model={},
            as_of=as_of
        )
