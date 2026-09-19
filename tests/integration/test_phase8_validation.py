import pytest
from datetime import datetime, timezone

from app.research.models import ResearchExperiment, ValidationResult
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics, AttributionMetrics
from app.research.consistency import EvidenceConsistencyValidator, EvidenceConsistencyReport
from app.research.comparator import CrossExperimentComparator, ComparabilityStatus
from app.research.evidence import ResearchEvidenceEvaluator, EvidenceConclusion

def create_base_experiment(trades: int = 40, pnl: float = 100.0, pf: float = 1.5, valid: bool = True, comm: float = 0.0) -> ResearchExperiment:
    oos_report = FullAnalyticsReport(
        backtest_id="test_exp",
        trade_metrics=TradeMetrics(
            total_trades=trades, winning_trades=trades//2, losing_trades=trades//2, win_rate=50.0,
            gross_pnl=pnl + comm, net_pnl=pnl, total_commission=comm, total_slippage=0.0,
            profit_factor=pf, max_consecutive_losses=2, average_pnl=pnl/max(1, trades),
            average_win=1.0, average_loss=-1.0, largest_win=2.0, largest_loss=-2.0,
            max_consecutive_wins=2, average_holding_hours=24.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=1000, final_equity=1000+pnl, total_return_pct=pnl/10,
            max_drawdown_pct=5.0, average_drawdown_pct=2.5, absolute_pnl=pnl,
            max_drawdown_amount=50.0, time_in_drawdown_pct=10.0, recovery_periods=5
        ),
        strategy_attribution=[AttributionMetrics(category="Strategy", label="Strat", sample_size=trades, total_pnl=pnl, win_rate=50.0, profit_factor=pf, average_pnl=pnl/max(1, trades))],
        regime_attribution=[], signal_bucket_attribution=[], intelligence_attribution=[], failure_findings=[], strategy_comparisons=[],
        telemetry_snapshot={"stage_counts": {"PAPER_TRADES": trades}}
    )
    
    return ResearchExperiment(
        experiment_id="test_exp", dataset_id="ds_1", dataset_identity={"hash": "ds_1"}, symbols=["BTC"], timeframe="1h", strategy="Strat", configuration="conf",
        starting_capital=1000.0, random_seed=42, created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[ValidationResult(is_valid=valid, errors=[], warnings=[], row_count=100, symbol="BTC")],
        out_of_sample_report=oos_report
    )

def test_consistency_valid():
    exp = create_base_experiment()
    report = EvidenceConsistencyValidator.validate(exp)
    assert report.is_consistent is True
    assert len(report.inconsistencies) == 0

def test_consistency_mismatch_trades():
    exp = create_base_experiment(trades=40)
    exp.out_of_sample_report.telemetry_snapshot["stage_counts"]["PAPER_TRADES"] = 50
    report = EvidenceConsistencyValidator.validate(exp)
    assert report.is_consistent is False
    assert any("Telemetry trade count" in i for i in report.inconsistencies)

def test_consistency_mismatch_strategy():
    exp = create_base_experiment()
    exp.strategy = "Strat_Different"
    report = EvidenceConsistencyValidator.validate(exp)
    assert any("Metadata strategy" in w for w in report.warnings) # We implemented it as warning

def test_missing_telemetry_legacy_record():
    exp = create_base_experiment()
    exp.out_of_sample_report.telemetry_snapshot = None
    report = EvidenceConsistencyValidator.validate(exp)
    assert report.is_consistent is True

def test_valid_accounting():
    exp = create_base_experiment(pnl=100.0, comm=10.0) # net = 100, gross = 110, comm = 10
    report = EvidenceConsistencyValidator.validate(exp)
    assert report.is_consistent is True

def test_invalid_accounting():
    exp = create_base_experiment(pnl=100.0, comm=10.0)
    exp.out_of_sample_report.trade_metrics.net_pnl = 150.0 # Bad math
    report = EvidenceConsistencyValidator.validate(exp)
    assert report.is_consistent is False
    assert any("Accounting mismatch" in i for i in report.inconsistencies)

def test_pf_gt_1_net_lt_0():
    # PF > 1 but Net PnL < 0 due to commissions
    exp = create_base_experiment(pnl=-5.0, comm=10.0, pf=1.2) # gross = 5.0, net = -5.0
    report = EvidenceConsistencyValidator.validate(exp)
    assert report.is_consistent is True # NOT a software issue!
    
    # Evaluate it
    eval_summary = ResearchEvidenceEvaluator.evaluate(exp)
    # Since OOS Trades = 40, and Net PnL < 0, it should be STRATEGY_MODEL_WEAKNESS, NOT SOFTWARE ISSUE
    assert eval_summary.conclusion == EvidenceConclusion.STRATEGY_MODEL_WEAKNESS

def test_gross_not_equal_net():
    exp = create_base_experiment(pnl=100.0, comm=10.0)
    # Gross = 110, Net = 100
    report = EvidenceConsistencyValidator.validate(exp)
    assert report.is_consistent is True

def test_comparable_experiments():
    exp1 = create_base_experiment()
    exp2 = create_base_experiment()
    exp2.experiment_id = "test_exp_2"
    
    comp = CrossExperimentComparator.compare(exp1, exp2)
    assert comp.comparability == ComparabilityStatus.COMPARABLE

def test_different_dataset():
    exp1 = create_base_experiment()
    exp2 = create_base_experiment()
    exp2.dataset_identity = {"hash": "ds_2"}
    
    comp = CrossExperimentComparator.compare(exp1, exp2)
    assert comp.comparability == ComparabilityStatus.NOT_COMPARABLE

def test_seed_difference():
    exp1 = create_base_experiment()
    exp2 = create_base_experiment()
    exp2.random_seed = 43
    
    comp = CrossExperimentComparator.compare(exp1, exp2)
    assert comp.comparability == ComparabilityStatus.LIMITED_COMPARABILITY
    assert any("Seed mismatch" in d for d in comp.differences)
