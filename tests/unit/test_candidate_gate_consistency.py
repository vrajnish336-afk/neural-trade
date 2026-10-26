import pytest
from datetime import datetime, timezone
from app.research.models import (
    ResearchExperiment, ChampionChallengerResult, WalkForwardResult, DataSplit
)
from app.research.challenger import ChampionChallengerValidator
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics

def _make_report(exp_id: str, return_pct: float, dd_pct: float, trades: int, pf: float = 1.5):
    return FullAnalyticsReport(
        backtest_id=exp_id,
        trade_metrics=TradeMetrics(
            total_trades=trades, winning_trades=int(trades * 0.5), losing_trades=int(trades * 0.5),
            win_rate=50.0, gross_pnl=return_pct, net_pnl=return_pct, total_commission=0.0, total_slippage=0.0,
            profit_factor=pf, max_consecutive_losses=2,
            average_pnl=return_pct / trades if trades > 0 else 0.0,
            average_win=1.0, average_loss=-0.5, largest_win=2.0, largest_loss=-1.0,
            max_consecutive_wins=3, average_holding_hours=24.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=1000.0, final_equity=1000.0 * (1 + return_pct / 100.0),
            total_return_pct=return_pct, max_drawdown_pct=dd_pct,
            average_drawdown_pct=dd_pct / 2, absolute_pnl=1000.0 * (return_pct / 100.0),
            max_drawdown_amount=1000.0 * (dd_pct / 100.0), time_in_drawdown_pct=10.0, recovery_periods=5
        ),
        strategy_attribution=[],
        regime_attribution=[],
        signal_bucket_attribution=[],
        intelligence_attribution=[],
        failure_findings=[],
        strategy_comparisons=[]
    )

def _make_experiment(exp_id: str, return_pct: float, dd_pct: float, trades: int, folds=None):
    rep = _make_report(exp_id, return_pct, dd_pct, trades)
    return ResearchExperiment(
        experiment_id=exp_id, dataset_id="dataset_common", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="conf", starting_capital=1000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=rep,
        walk_forward_results=folds if folds is not None else [],
        configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

def _make_fold(window_id: str, trades: int, pf: float):
    rep = _make_report(f"wf_{window_id}", 5.0, 2.0, trades, pf=pf)
    split = DataSplit(name="s1", symbol="BTC", start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc), row_count=100)
    return WalkForwardResult(
        window_id=window_id,
        train_split=split, validation_split=split, test_split=split,
        train_report=rep, validation_report=rep, test_report=rep
    )

def test_missing_fold_evidence_cannot_promote():
    champ = _make_experiment("champ", 10.0, 5.0, 50, folds=[_make_fold("1", 25, 1.8)])
    chall = _make_experiment("chall", 15.0, 4.0, 60, folds=[])  # Missing fold evidence!

    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)

    assert result.decision != "PROMOTE"
    assert result.decision == "INCONCLUSIVE"
    assert "Missing Walk-Forward Fold Evidence" in result.decision_reasons
    assert result.scorecard["has_fold_evidence"] is False

def test_severe_loss_fold_rejects_candidate():
    champ = _make_experiment("champ", 10.0, 5.0, 50, folds=[_make_fold("1", 25, 1.8)])
    # Challenger beats return and drawdown, but has a fold with PF=0.00 (< 0.5)
    f1 = _make_fold("1", 30, 2.0)
    f2 = _make_fold("2", 10, 0.0)  # Catastrophic fold!
    chall = _make_experiment("chall", 18.0, 4.5, 60, folds=[f1, f2])

    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)

    assert result.decision == "REJECT"
    assert any("Severe Loss in Validation Fold" in r for r in result.decision_reasons)
    assert result.scorecard["has_severe_loss"] is True

def test_empty_fold_with_zero_trades_does_not_trigger_severe_loss():
    champ = _make_experiment("champ", 10.0, 5.0, 50, folds=[_make_fold("1", 25, 1.8)])
    f1 = _make_fold("1", 35, 1.8)
    f2 = _make_fold("2", 0, 0.0)  # Empty fold: 0 trades
    chall = _make_experiment("chall", 16.0, 4.0, 50, folds=[f1, f2])

    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)

    assert result.scorecard["has_severe_loss"] is False
    assert result.decision == "PROMOTE"

def test_valid_candidate_with_robust_folds_promotes():
    champ = _make_experiment("champ", 10.0, 5.0, 50, folds=[_make_fold("1", 25, 1.8)])
    f1 = _make_fold("1", 25, 1.6)
    f2 = _make_fold("2", 30, 1.7)
    chall = _make_experiment("chall", 16.0, 4.0, 55, folds=[f1, f2])

    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)

    assert result.decision == "PROMOTE"
    assert result.scorecard["has_fold_evidence"] is True
    assert result.scorecard["has_severe_loss"] is False

def test_dict_and_custom_fold_format_supported():
    trades, pf = ChampionChallengerValidator._extract_fold_metrics({"trades": 25, "pf": 1.5})
    assert trades == 25
    assert pf == 1.5

    trades_bad, pf_bad = ChampionChallengerValidator._extract_fold_metrics({"total_trades": 5, "profit_factor": 0.2})
    assert trades_bad == 5
    assert pf_bad == 0.2

    # Verify validator rejects when custom fold object with severe loss is in challenger
    champ = _make_experiment("champ", 10.0, 5.0, 50, folds=[_make_fold("1", 25, 1.5)])
    chall = _make_experiment("chall", 16.0, 4.0, 55, folds=[])
    
    class CustomFold:
        def __init__(self, t, p):
            self.trades = t
            self.profit_factor = p
            
    chall.walk_forward_results = [CustomFold(10, 0.1)]
    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)

    assert result.decision == "REJECT"
    assert result.scorecard["has_severe_loss"] is True
