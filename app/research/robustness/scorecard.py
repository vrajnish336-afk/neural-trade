import numpy as np
from typing import List, Dict
from app.research.robustness.models import (
    SeedTestResult, CostStressScenario, MonteCarloRobustnessResult, 
    RobustnessScorecard
)

def evaluate_robustness(
    experiment_id: str,
    symbol: str,
    seed_results: List[SeedTestResult],
    cost_results: List[CostStressScenario],
    mc_result: MonteCarloRobustnessResult
) -> RobustnessScorecard:
    """
    Deterministically converts research metrics into a categorical Robustness Scorecard.
    """
    # 1. Cross-Seed Stability
    returns = [r.return_pct for r in seed_results]
    positive_seeds = sum(1 for r in returns if r > 0)
    seed_stability = "STRONG"
    if positive_seeds < len(returns) // 2:
        seed_stability = "FRAGILE"
    elif positive_seeds < len(returns):
        seed_stability = "MIXED"
        
    # 2. Cost Resilience
    cost_resilience = "STRONG"
    if cost_results:
        # Check 3x cost
        mult3 = next((c for c in cost_results if c.multiplier == 3.0), None)
        if mult3:
            if mult3.return_pct <= 0:
                cost_resilience = "FRAGILE"
            elif mult3.degradation_pct > 50:
                cost_resilience = "MIXED"
                
    # 3. Monte Carlo
    mc_stability = "STRONG"
    if mc_result.p05_return_pct < 0:
        mc_stability = "FRAGILE"
    elif mc_result.p25_return_pct < (mc_result.median_return_pct * 0.5):
        mc_stability = "MIXED"
        
    # 4. Sample Size
    avg_trades = np.mean([r.trades for r in seed_results]) if seed_results else 0
    sample_size = "STRONG"
    if avg_trades < 10:
        sample_size = "INSUFFICIENT"
    elif avg_trades < 30:
        sample_size = "WEAK"
        
    # Overall 
    overall = "STRONG_EVIDENCE"
    statuses = [seed_stability, cost_resilience, mc_stability, sample_size]
    
    if "INSUFFICIENT" in statuses:
        overall = "INSUFFICIENT_DATA"
    elif "FRAGILE" in statuses:
        overall = "FRAGILE"
    elif "MIXED" in statuses or "WEAK" in statuses:
        overall = "MIXED_EVIDENCE"
        
    return RobustnessScorecard(
        experiment_id=experiment_id,
        symbol=symbol,
        overall_status=overall,
        cross_seed_stability=seed_stability,
        parameter_sensitivity="NOT_IMPLEMENTED_YET",
        cost_resilience=cost_resilience,
        walk_forward_consistency="NOT_IMPLEMENTED_YET",
        monte_carlo_stability=mc_stability,
        sample_size_adequacy=sample_size,
        statistical_uncertainty={
            "mc_median": f"{mc_result.median_return_pct:.2f}%",
            "mc_p05": f"{mc_result.p05_return_pct:.2f}%",
            "mc_p95": f"{mc_result.p95_return_pct:.2f}%"
        }
    )
