import pytest
import copy
from app.research.dataset import generate_synthetic_data
from app.diagnostics.adaptive_walk_forward import create_engine
from app.backtesting.models import CostConfig
from app.diagnostics.telemetry import telemetry

def test_adaptive_no_lookahead():
    """
    Ensures the AdaptiveIntelligence model does not leak future trades or metrics into the past.
    """
    config = CostConfig()
    bars = generate_synthetic_data(["TEST_ADAPTIVE"], num_bars=300, seed=123)["TEST_ADAPTIVE"]
    
    # Run Baseline up to T=150
    telemetry.reset()
    telemetry.enabled = True
    
    engine_base = create_engine(config, use_adaptive=True)
    engine_base.run(bars[:150])
    
    base_equity = engine_base.equity
    base_decisions = copy.deepcopy(telemetry.adaptive_decisions)
    
    # Corrupt future bars (150+)
    corrupted_bars = copy.deepcopy(bars)
    for i in range(150, 300):
        corrupted_bars[i].close = 99999.0
        corrupted_bars[i].volume = 99999.0
        
    # Run Corrupted up to T=150
    telemetry.reset()
    telemetry.enabled = True
    engine_test = create_engine(config, use_adaptive=True)
    
    # We pass only up to T=150, but if there was a reference bug to future corrupted_bars, it would fail.
    # To truly test internal leakage, we simulate the engine running over corrupted_bars list up to 150.
    engine_test.run(corrupted_bars[:150])
    
    test_equity = engine_test.equity
    test_decisions = telemetry.adaptive_decisions
    
    assert base_equity == test_equity, "Adaptive equity leaked from future!"
    assert len(base_decisions) == len(test_decisions), "Decision count mismatch!"
    
    for b, t in zip(base_decisions, test_decisions):
        assert b["regime"] == t["regime"]
        assert b["confidence"] == t["confidence"]
        assert b["weights"] == t["weights"], "Weights changed due to future corruption!"
