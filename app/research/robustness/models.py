from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class MonteCarloRobustnessResult(BaseModel):
    simulations: int
    median_return_pct: float
    p05_return_pct: float
    p25_return_pct: float
    p75_return_pct: float
    p95_return_pct: float
    median_drawdown_pct: float
    p95_drawdown_pct: float
    worst_drawdown_pct: float

class CostStressScenario(BaseModel):
    multiplier: float
    total_trades: int
    return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    degradation_pct: float

class ParameterSensitivityResult(BaseModel):
    parameter_name: str
    baseline_value: str
    tested_value: str
    train_result: Dict[str, float]
    validation_result: Dict[str, float]
    test_result: Dict[str, float]
    trade_count: int
    return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float

class WalkForwardWindowResult(BaseModel):
    window_id: int
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str
    strategy: str
    adaptive_state: str
    strategy_weights: Dict[str, float]
    trades: int
    return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float

class SeedTestResult(BaseModel):
    seed: int
    trades: int
    return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float

class StrategyRobustnessResult(BaseModel):
    strategy_name: str
    sample_size: int
    return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    regime_distribution: Dict[str, int]
    failure_count: int
    status: str # ROBUST, MIXED, FRAGILE, INSUFFICIENT_SAMPLE

class RobustnessScorecard(BaseModel):
    experiment_id: str
    symbol: str
    overall_status: str # STRONG_EVIDENCE, MODERATE_EVIDENCE, MIXED_EVIDENCE, FRAGILE, INSUFFICIENT_DATA
    cross_seed_stability: str
    parameter_sensitivity: str
    cost_resilience: str
    walk_forward_consistency: str
    monte_carlo_stability: str
    sample_size_adequacy: str
    statistical_uncertainty: Dict[str, str]
