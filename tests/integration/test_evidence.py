import pytest
from datetime import datetime, timezone
import subprocess
from pathlib import Path

from app.research.models import ResearchExperiment, ValidationResult, StressTestResult, WalkForwardResult, DataSplit
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics, AttributionMetrics
from app.research.evidence import ResearchEvidenceEvaluator, EvidenceConclusion, EvidenceStatus

CLI_PATH = Path(__file__).parent.parent.parent / "cli.py"

def run_cli(*args, **kwargs):
    return subprocess.run(
        ["python", str(CLI_PATH)] + list(args),
        capture_output=True,
        text=True
    )

def create_base_experiment(trades: int = 40, pnl: float = 100.0, pf: float = 1.5, valid: bool = True, regimes: int = 2) -> ResearchExperiment:
    regime_list = []
    for i in range(regimes):
        regime_list.append(AttributionMetrics(category="Regime", label=f"REGIME_{i}", sample_size=trades//regimes, total_pnl=pnl/regimes, win_rate=50.0, profit_factor=pf, average_pnl=pnl/regimes/max(1, trades//regimes)))
        
    oos_report = FullAnalyticsReport(
        backtest_id="test_exp",
        trade_metrics=TradeMetrics(
            total_trades=trades, winning_trades=trades//2, losing_trades=trades//2, win_rate=50.0,
            gross_pnl=pnl, net_pnl=pnl, total_commission=0.0, total_slippage=0.0,
            profit_factor=pf, max_consecutive_losses=2, average_pnl=pnl/max(1, trades),
            average_win=1.0, average_loss=-1.0, largest_win=2.0, largest_loss=-2.0,
            max_consecutive_wins=2, average_holding_hours=24.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=1000, final_equity=1000+pnl, total_return_pct=pnl/10,
            max_drawdown_pct=5.0, average_drawdown_pct=2.5, absolute_pnl=pnl,
            max_drawdown_amount=50.0, time_in_drawdown_pct=10.0, recovery_periods=5
        ),
        strategy_attribution=[],
        regime_attribution=regime_list,
        signal_bucket_attribution=[], intelligence_attribution=[], failure_findings=[], strategy_comparisons=[]
    )
    
    dt = datetime.now(timezone.utc)
    ds = DataSplit(name="split", symbol="BTC", start_time=dt, end_time=dt, row_count=100)
    wf_result = WalkForwardResult(
        window_id="w1", train_split=ds, validation_split=ds, test_split=ds,
        train_report=oos_report, validation_report=oos_report, test_report=oos_report
    )
    
    stress_result = StressTestResult(
        condition_name="cost", baseline_return=1.0, stress_return=0.5, degradation_pct=50.0,
        baseline_win_rate=50.0, stress_win_rate=40.0
    )
    
    return ResearchExperiment(
        experiment_id="test_exp",
        dataset_id="ds_1",
        symbols=["BTC"],
        timeframe="1h",
        strategy="Strat",
        configuration="conf",
        starting_capital=1000.0,
        random_seed=42,
        created_at=dt,
        status="COMPLETED",
        validation_results=[ValidationResult(is_valid=valid, errors=[], warnings=[], row_count=100, symbol="BTC")],
        out_of_sample_report=oos_report,
        walk_forward_results=[wf_result],
        stress_test_results=[stress_result],
        seeds={"42": {}, "43": {}} # length 2
    )

def test_insufficient_evidence():
    exp = create_base_experiment(trades=10) # < 30
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(exp)
    
    assert summary.conclusion == EvidenceConclusion.INSUFFICIENT_EVIDENCE
    assert summary.status == EvidenceStatus.INSUFFICIENT

def test_strategy_weakness_pf():
    exp = create_base_experiment(trades=40, pf=0.8, pnl=100.0)
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(exp)
    
    assert summary.conclusion == EvidenceConclusion.STRATEGY_MODEL_WEAKNESS
    assert summary.status == EvidenceStatus.WEAK
    
def test_strategy_weakness_pnl():
    exp = create_base_experiment(trades=40, pf=1.5, pnl=-50.0)
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(exp)
    
    assert summary.conclusion == EvidenceConclusion.STRATEGY_MODEL_WEAKNESS
    assert summary.status == EvidenceStatus.WEAK

def test_software_issue():
    exp = create_base_experiment(valid=False)
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(exp)
    
    assert summary.conclusion == EvidenceConclusion.SOFTWARE_ACCOUNTING_ISSUE
    assert summary.status == EvidenceStatus.INSUFFICIENT
    
def test_verified_result():
    exp = create_base_experiment()
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(exp)
    
    assert summary.conclusion == EvidenceConclusion.VERIFIED_RESULT
    assert summary.status == EvidenceStatus.STRONG

def test_research_limitation():
    # Only 1 regime
    exp = create_base_experiment(regimes=1)
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(exp)
    
    assert summary.conclusion == EvidenceConclusion.RESEARCH_LIMITATION
    assert summary.status == EvidenceStatus.MODERATE
    assert any("regime" in r for r in summary.limitations)
    
def test_missing_legacy_fields():
    # Construct without newer fields
    exp = create_base_experiment()
    delattr(exp, 'walk_forward_results')
    delattr(exp, 'stress_test_results')
    delattr(exp, 'seeds')
    
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(exp)
    
    assert summary.conclusion == EvidenceConclusion.RESEARCH_LIMITATION
    assert summary.status == EvidenceStatus.MODERATE
    assert summary.robustness.walk_forward.value == "NOT_AVAILABLE"

def test_deterministic():
    exp = create_base_experiment()
    evaluator = ResearchEvidenceEvaluator()
    summary1 = evaluator.evaluate(exp)
    summary2 = evaluator.evaluate(exp)
    
    assert summary1.model_dump_json() == summary2.model_dump_json()

def test_cli_evaluate_invalid():
    res = run_cli("evaluate", "nonexistent")
    assert res.returncode == 1
    assert "Error: Experiment not found" in res.stdout
