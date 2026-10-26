import os
import pytest
from datetime import datetime, timezone
from app.research.challenger import ChampionChallengerValidator
from app.research.models import ResearchExperiment, DataSplit, WalkForwardResult
from app.research.robustness.artifact import load_evidence_from_json
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics

def _make_report(exp_id: str, return_pct: float, dd_pct: float, trades: int, pf: float = 1.5, gross_pnl: float = 100.0, net_pnl: float = 100.0):
    return FullAnalyticsReport(
        backtest_id=exp_id,
        trade_metrics=TradeMetrics(
            total_trades=trades, winning_trades=int(trades * 0.6), losing_trades=int(trades * 0.4),
            win_rate=60.0, gross_pnl=gross_pnl, net_pnl=net_pnl, total_commission=20.0, total_slippage=30.0,
            profit_factor=pf, max_consecutive_losses=2,
            average_pnl=net_pnl / trades if trades > 0 else 0.0,
            average_win=2.0, average_loss=-1.0, largest_win=5.0, largest_loss=-3.0,
            max_consecutive_wins=3, average_holding_hours=12.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=10000.0, final_equity=10000.0 * (1.0 + return_pct / 100.0),
            total_return_pct=return_pct, max_drawdown_pct=dd_pct,
            average_drawdown_pct=dd_pct / 2.0, absolute_pnl=10000.0 * (return_pct / 100.0),
            max_drawdown_amount=10000.0 * (dd_pct / 100.0), time_in_drawdown_pct=10.0, recovery_periods=2
        ),
        strategy_attribution=[], regime_attribution=[], signal_bucket_attribution=[],
        intelligence_attribution=[], failure_findings=[], strategy_comparisons=[]
    )

def _make_champ():
    rep = _make_report("champ", return_pct=10.0, dd_pct=5.0, trades=50, pf=1.5, net_pnl=1000.0)
    split = DataSplit(name="s", symbol="BTC", start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc), row_count=100)
    wf_fold = WalkForwardResult(window_id="1", train_split=split, validation_split=split, test_split=split,
                                 train_report=rep, validation_report=rep, test_report=rep)
    return ResearchExperiment(
        experiment_id="champ", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=rep, walk_forward_results=[wf_fold],
        configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

def test_smoke_artifact_candidate_remains_rejected():
    """Verify that candidate with real smoke artifact 4dd5d272-1090-4911-b06f-c84ad3ba8744 is strictly REJECTED."""
    art_path = "reports/smoke_walk_forward_artifact.json"
    assert os.path.exists(art_path)
    art = load_evidence_from_json(art_path)
    assert art is not None
    assert art.artifact_id == "4dd5d272-1090-4911-b06f-c84ad3ba8744"
    assert art.aggregate.total_trades == 10
    assert abs(art.aggregate.profit_factor - 0.6128511253213667) < 1e-6
    assert abs(art.aggregate.net_pnl - (-842.2478706995413)) < 1e-6

    champ = _make_champ()

    chall_rep = FullAnalyticsReport(
        backtest_id="chall",
        trade_metrics=TradeMetrics(
            total_trades=art.aggregate.total_trades, winning_trades=art.aggregate.wins, losing_trades=art.aggregate.losses, win_rate=20.0,
            gross_pnl=art.aggregate.gross_profit, net_pnl=art.aggregate.net_pnl, total_commission=194.76, total_slippage=194.76,
            profit_factor=art.aggregate.profit_factor, max_consecutive_losses=8, average_pnl=art.aggregate.expectancy,
            average_win=666.0, average_loss=-271.0, largest_win=965.0, largest_loss=-346.0, max_consecutive_wins=1, average_holding_hours=24.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=10000.0, final_equity=9157.75, total_return_pct=-8.42, max_drawdown_pct=art.aggregate.max_drawdown_pct,
            average_drawdown_pct=3.0, absolute_pnl=art.aggregate.net_pnl, max_drawdown_amount=738.0, time_in_drawdown_pct=50.0, recovery_periods=0
        ),
        strategy_attribution=[], regime_attribution=[], signal_bucket_attribution=[],
        intelligence_attribution=[], failure_findings=[], strategy_comparisons=[]
    )
    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="AdaptiveEnsemble", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep, walk_forward_artifact=art,
        configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

    validator = ChampionChallengerValidator()
    res = validator.evaluate(champ, chall)

    assert res.decision == "REJECT"
    assert res.scorecard["has_severe_loss"] is True
    assert res.scorecard["oos_trades"]["chall"] == 10
    assert any("Severe Loss in Validation Fold" in r for r in res.decision_reasons)
    assert "Insufficient Sample Size (<30 trades)" in res.decision_reasons
    assert "Lower/Equal OOS Return" in res.decision_reasons

def test_pre_cost_metrics_never_justify_promotion():
    """Verify that flattering pre-cost metrics cannot justify promotion if post-cost metrics degrade."""
    champ = _make_champ()

    # Challenger has high pre-cost gross PnL ($2500) and pre-cost PF, but post-cost net return is negative (-5.0%)
    chall_rep = _make_report("chall", return_pct=-5.0, dd_pct=4.0, trades=60, pf=0.8, gross_pnl=2500.0, net_pnl=-500.0)
    split = DataSplit(name="s", symbol="BTC", start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc), row_count=100)
    valid_fold = WalkForwardResult(window_id="1", train_split=split, validation_split=split, test_split=split,
                                    train_report=chall_rep, validation_report=chall_rep, test_report=chall_rep)

    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep, walk_forward_results=[valid_fold],
        configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

    validator = ChampionChallengerValidator()
    res = validator.evaluate(champ, chall)

    # Must NOT promote despite pre-cost gross PnL being high
    assert res.decision != "PROMOTE"
    assert res.decision == "REJECT"
    assert "Lower/Equal OOS Return" in res.decision_reasons

def test_missing_evidence_results_in_inconclusive():
    """Verify that a candidate missing walk-forward fold evidence results in INCONCLUSIVE."""
    champ = _make_champ()
    # Challenger beats return and drawdown with sufficient trades, but has 0 fold evidence
    chall_rep = _make_report("chall", return_pct=18.0, dd_pct=4.0, trades=60, pf=1.8)
    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep, walk_forward_results=[],
        configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

    validator = ChampionChallengerValidator()
    res = validator.evaluate(champ, chall)

    assert res.decision == "INCONCLUSIVE"
    assert "Missing Walk-Forward Fold Evidence" in res.decision_reasons
    assert res.scorecard["has_fold_evidence"] is False

def test_populated_fold_severe_loss_rejects():
    """Verify that any populated fold with post-cost PF < 0.5 triggers REJECT."""
    champ = _make_champ()

    chall_rep = _make_report("chall", return_pct=20.0, dd_pct=4.0, trades=60, pf=1.9)
    split = DataSplit(name="s", symbol="BTC", start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc), row_count=100)

    good_fold_rep = _make_report("f1", return_pct=10.0, dd_pct=2.0, trades=30, pf=1.8)
    f1 = WalkForwardResult(window_id="1", train_split=split, validation_split=split, test_split=split,
                           train_report=good_fold_rep, validation_report=good_fold_rep, test_report=good_fold_rep)

    # Populated fold with PF = 0.35 (< 0.5)
    bad_fold_rep = _make_report("f2", return_pct=-8.0, dd_pct=6.0, trades=15, pf=0.35)
    f2 = WalkForwardResult(window_id="2", train_split=split, validation_split=split, test_split=split,
                           train_report=bad_fold_rep, validation_report=bad_fold_rep, test_report=bad_fold_rep)

    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep, walk_forward_results=[f1, f2],
        configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

    validator = ChampionChallengerValidator()
    res = validator.evaluate(champ, chall)

    assert res.decision == "REJECT"
    assert res.scorecard["has_severe_loss"] is True
    assert any("Severe Loss in Validation Fold" in r for r in res.decision_reasons)

def test_minimum_sample_size_gate_enforced():
    """Verify that a candidate with < 30 trades cannot be promoted (INCONCLUSIVE)."""
    champ = _make_champ()

    # Challenger beats return and drawdown with valid fold, but only 20 trades (< 30)
    chall_rep = _make_report("chall", return_pct=16.0, dd_pct=4.0, trades=20, pf=1.8)
    split = DataSplit(name="s", symbol="BTC", start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc), row_count=100)
    f1 = WalkForwardResult(window_id="1", train_split=split, validation_split=split, test_split=split,
                           train_report=chall_rep, validation_report=chall_rep, test_report=chall_rep)

    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep, walk_forward_results=[f1],
        configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

    validator = ChampionChallengerValidator()
    res = validator.evaluate(champ, chall)

    assert res.decision == "INCONCLUSIVE"
    assert "Insufficient Sample Size (<30 trades)" in res.decision_reasons
