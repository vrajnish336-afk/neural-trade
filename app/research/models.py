from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.analytics.models import FullAnalyticsReport

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    row_count: int
    symbol: str

class DataSplit(BaseModel):
    name: str
    symbol: str
    start_time: datetime
    end_time: datetime
    row_count: int

class WalkForwardResult(BaseModel):
    window_id: str
    train_split: DataSplit
    validation_split: DataSplit
    test_split: DataSplit
    train_report: FullAnalyticsReport
    validation_report: FullAnalyticsReport
    test_report: FullAnalyticsReport

class StressTestResult(BaseModel):
    condition_name: str
    baseline_return: float
    stress_return: float
    degradation_pct: float
    baseline_win_rate: float
    stress_win_rate: float

class ParameterSensitivityRun(BaseModel):
    config_id: str
    parameters: str
    train_return: float
    validation_return: float
    test_return: float
    overfit_warning: bool

class EnvironmentLineage(BaseModel):
    python_version: str
    os_name: str

class CodeLineage(BaseModel):
    commit_hash: Optional[str] = None
    is_dirty: Optional[bool] = None

class StrategyLineage(BaseModel):
    strategy_name: str
    parameters: Dict[str, Any]

class ConfigurationLineage(BaseModel):
    cost_model: Dict[str, float]
    risk_model: Dict[str, float]
    capital: float

class ResearchLineage(BaseModel):
    environment: EnvironmentLineage
    code: CodeLineage
    strategy: StrategyLineage
    configuration: ConfigurationLineage

class ResearchExperiment(BaseModel):
    experiment_id: str
    experiment_name: str = "Unnamed Experiment"
    experiment_type: str = "BACKTEST"
    description: str = ""
    code_version: str = "1.0.0"
    dataset_id: str
    dataset_identity: Dict[str, Any] = {}
    symbols: List[str]
    timeframe: str
    strategy: str
    configuration: str
    configuration_snapshot: Dict[str, Any] = {}
    starting_capital: float
    random_seed: int
    seeds: Dict[str, Any] = {}
    lineage: Optional[ResearchLineage] = None
    created_at: datetime
    status: str
    classification: str = "MIXED_EVIDENCE"
    notes: str = ""
    reproducibility: Dict[str, Any] = {}
    validation_results: List[ValidationResult]
    out_of_sample_report: Optional[FullAnalyticsReport] = None
    walk_forward_results: List[WalkForwardResult] = []
    stress_test_results: List[StressTestResult] = []
    parameter_sensitivity: List[ParameterSensitivityRun] = []
    
def get_sample_size_warning(n: int) -> str:
    if n < 5: return "VERY_LOW_SAMPLE"
    if n < 20: return "LOW_SAMPLE"
    if n < 50: return "MODERATE_SAMPLE"
    return "LARGER_SAMPLE"

class ChampionChallengerResult(BaseModel):
    comparison_id: str
    timestamp: datetime
    champion_experiment_id: str
    challenger_experiment_id: str
    dataset_id: str
    decision: str
    decision_reasons: List[str]
    scorecard: Dict[str, Any]

