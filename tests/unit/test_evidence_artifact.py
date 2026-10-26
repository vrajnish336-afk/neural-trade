import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar
from app.research.models import ResearchExperiment
from app.research.challenger import ChampionChallengerValidator
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics
from app.research.robustness.artifact import (
    FoldBoundary,
    FoldEvidenceMetrics,
    AggregateEvidenceMetrics,
    WalkForwardEvidenceArtifact,
    compute_dataset_fingerprint,
    get_current_code_revision,
    build_evidence_artifact,
    save_evidence_artifact,
    load_evidence_artifact
)

def _make_deterministic_bars(count=10):
    t0 = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
    return [
        MarketBar(
            symbol="BTC_USDT",
            timestamp=t0 + timedelta(hours=i),
            open=100.0 + i,
            high=105.0 + i,
            low=95.0 + i,
            close=102.0 + i,
            volume=100.0
        )
        for i in range(count)
    ]

def _make_sample_fold(window_id: int, trades: int, wins: int, losses: int, gp: float, gl: float, net: float, costs: float, pf: float = 1.5):
    return FoldEvidenceMetrics(
        window_id=window_id,
        boundaries=FoldBoundary(
            train_start=f"2023-01-0{window_id}T00:00:00Z",
            train_end=f"2023-01-0{window_id}T12:00:00Z",
            validation_start=f"2023-01-0{window_id}T12:00:00Z",
            validation_end=f"2023-01-0{window_id}T18:00:00Z",
            test_start=f"2023-01-0{window_id}T18:00:00Z",
            test_end=f"2023-01-0{window_id+1}T00:00:00Z"
        ),
        trades=trades,
        wins=wins,
        losses=losses,
        profit_factor=pf,
        expectancy=net / trades if trades > 0 else 0.0,
        max_drawdown_pct=5.0,
        gross_profit=gp,
        gross_loss=gl,
        net_pnl=net,
        entry_costs=costs * 0.4,
        exit_costs=costs * 0.4,
        slippage_costs=costs * 0.2,
        total_costs=costs
    )

def test_dataset_fingerprint_deterministic():
    bars1 = _make_deterministic_bars(10)
    bars2 = _make_deterministic_bars(10)
    
    fp1 = compute_dataset_fingerprint(bars1)
    fp2 = compute_dataset_fingerprint(bars2)
    assert fp1 == fp2
    assert len(fp1) == 64

    # Modified bar must yield different fingerprint
    bars_mod = _make_deterministic_bars(10)
    bars_mod[-1].close += 10.0
    fp_mod = compute_dataset_fingerprint(bars_mod)
    assert fp_mod != fp1

def test_code_revision_retrieval():
    rev = get_current_code_revision()
    assert isinstance(rev, str)
    assert len(rev) > 0

def test_reconciliation_exact_match():
    f1 = _make_sample_fold(1, trades=10, wins=6, losses=4, gp=100.0, gl=40.0, net=50.0, costs=10.0, pf=2.5)
    f2 = _make_sample_fold(2, trades=15, wins=8, losses=7, gp=150.0, gl=80.0, net=55.0, costs=15.0, pf=1.87)
    
    agg = AggregateEvidenceMetrics(
        total_trades=25,
        wins=14,
        losses=11,
        profit_factor=250.0 / 120.0,
        expectancy=105.0 / 25,
        max_drawdown_pct=7.0,
        gross_profit=250.0,
        gross_loss=120.0,
        net_pnl=105.0,
        total_costs=25.0
    )
    
    artifact = build_evidence_artifact(
        candidate_id="cand_1",
        strategy_name="TrendFollowing",
        parameters={"fast": 10, "slow": 30},
        dataset_fingerprint="abc123hash",
        folds=[f1, f2],
        aggregate=agg
    )
    
    assert artifact.reconciled is True
    assert len(artifact.folds) == 2
    assert artifact.aggregate.total_trades == 25

def test_reconciliation_mismatches_raise_error():
    f1 = _make_sample_fold(1, trades=10, wins=6, losses=4, gp=100.0, gl=40.0, net=50.0, costs=10.0)
    
    # Mismatch in trade count
    bad_agg_trades = AggregateEvidenceMetrics(
        total_trades=15, # Mismatch!
        wins=6, losses=4, profit_factor=2.5, expectancy=5.0,
        max_drawdown_pct=5.0, gross_profit=100.0, gross_loss=40.0, net_pnl=50.0, total_costs=10.0
    )
    with pytest.raises(ValueError, match="Trade count mismatch"):
        build_evidence_artifact("c1", "s1", {}, "fp", [f1], bad_agg_trades)

    # Mismatch in net PnL
    bad_agg_pnl = AggregateEvidenceMetrics(
        total_trades=10, wins=6, losses=4, profit_factor=2.5, expectancy=5.0,
        max_drawdown_pct=5.0, gross_profit=100.0, gross_loss=40.0, net_pnl=999.0, total_costs=10.0 # Mismatch!
    )
    with pytest.raises(ValueError, match="Net PnL mismatch"):
        build_evidence_artifact("c1", "s1", {}, "fp", [f1], bad_agg_pnl)

def test_artifact_persistence_sqlite_and_json():
    f1 = _make_sample_fold(1, trades=10, wins=6, losses=4, gp=100.0, gl=40.0, net=50.0, costs=10.0)
    agg = AggregateEvidenceMetrics(
        total_trades=10, wins=6, losses=4, profit_factor=2.5, expectancy=5.0,
        max_drawdown_pct=5.0, gross_profit=100.0, gross_loss=40.0, net_pnl=50.0, total_costs=10.0
    )
    artifact = build_evidence_artifact("c1", "s1", {"fast": 10}, "fp123", [f1], agg)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_research.db")
        json_path = os.path.join(tmpdir, "test_artifact.json")

        saved_id = save_evidence_artifact(artifact, db_path=db_path, json_path=json_path)
        assert saved_id == artifact.artifact_id
        assert os.path.exists(json_path)

        loaded = load_evidence_artifact(saved_id, db_path=db_path)
        assert loaded is not None
        assert loaded.candidate_id == "c1"
        assert loaded.parameters == {"fast": 10}
        assert len(loaded.folds) == 1
        assert loaded.aggregate.total_trades == 10

def test_artifact_integration_with_challenger_gate():
    champ_rep = FullAnalyticsReport(
        backtest_id="champ",
        trade_metrics=TradeMetrics(
            total_trades=50, winning_trades=25, losing_trades=25, win_rate=50.0,
            gross_pnl=10.0, net_pnl=10.0, total_commission=0.0, total_slippage=0.0, profit_factor=1.5,
            max_consecutive_losses=2, average_pnl=0.2, average_win=1.0, average_loss=-0.5,
            largest_win=2.0, largest_loss=-1.0, max_consecutive_wins=3, average_holding_hours=24.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=1000.0, final_equity=1100.0, total_return_pct=10.0, max_drawdown_pct=5.0,
            average_drawdown_pct=2.5, absolute_pnl=100.0, max_drawdown_amount=50.0, time_in_drawdown_pct=10.0, recovery_periods=5
        ),
        strategy_attribution=[], regime_attribution=[], signal_bucket_attribution=[],
        intelligence_attribution=[], failure_findings=[], strategy_comparisons=[]
    )
    champ = ResearchExperiment(
        experiment_id="champ", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="conf", starting_capital=1000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=champ_rep, walk_forward_results=[]
    )

    chall_rep = FullAnalyticsReport(
        backtest_id="chall",
        trade_metrics=TradeMetrics(
            total_trades=60, winning_trades=35, losing_trades=25, win_rate=58.3,
            gross_pnl=16.0, net_pnl=16.0, total_commission=0.0, total_slippage=0.0, profit_factor=1.8,
            max_consecutive_losses=2, average_pnl=0.27, average_win=1.0, average_loss=-0.5,
            largest_win=2.0, largest_loss=-1.0, max_consecutive_wins=3, average_holding_hours=24.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=1000.0, final_equity=1160.0, total_return_pct=16.0, max_drawdown_pct=4.0,
            average_drawdown_pct=2.0, absolute_pnl=160.0, max_drawdown_amount=40.0, time_in_drawdown_pct=10.0, recovery_periods=5
        ),
        strategy_attribution=[], regime_attribution=[], signal_bucket_attribution=[],
        intelligence_attribution=[], failure_findings=[], strategy_comparisons=[]
    )
    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC"], timeframe="1h",
        strategy="Strat", configuration="conf", starting_capital=1000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep
    )

    validator = ChampionChallengerValidator()

    # 1. Missing evidence -> INCONCLUSIVE
    res_missing = validator.evaluate(champ, chall)
    assert res_missing.decision == "INCONCLUSIVE"
    assert "Missing Walk-Forward Fold Evidence" in res_missing.decision_reasons

    # 2. Attach valid reconciled artifact -> PROMOTE
    f1 = _make_sample_fold(1, trades=30, wins=18, losses=12, gp=100.0, gl=50.0, net=45.0, costs=5.0, pf=2.0)
    f2 = _make_sample_fold(2, trades=30, wins=17, losses=13, gp=80.0, gl=50.0, net=25.0, costs=5.0, pf=1.6)
    agg = AggregateEvidenceMetrics(
        total_trades=60, wins=35, losses=25, profit_factor=180.0/100.0, expectancy=70.0/60,
        max_drawdown_pct=4.0, gross_profit=180.0, gross_loss=100.0, net_pnl=70.0, total_costs=10.0
    )
    artifact_valid = build_evidence_artifact("chall", "Strat", {}, "fp", [f1, f2], agg)
    chall.walk_forward_artifact = artifact_valid

    res_valid = validator.evaluate(champ, chall)
    assert res_valid.decision == "PROMOTE"

    # 3. Attach artifact with severe loss fold (PF = 0.2 < 0.5) -> REJECT
    f_bad = _make_sample_fold(2, trades=30, wins=5, losses=25, gp=10.0, gl=50.0, net=-45.0, costs=5.0, pf=0.2)
    agg_bad = AggregateEvidenceMetrics(
        total_trades=60, wins=23, losses=37, profit_factor=110.0/100.0, expectancy=0.0,
        max_drawdown_pct=15.0, gross_profit=110.0, gross_loss=100.0, net_pnl=0.0, total_costs=10.0
    )
    artifact_bad = build_evidence_artifact("chall", "Strat", {}, "fp", [f1, f_bad], agg_bad)
    chall.walk_forward_artifact = artifact_bad

    res_bad = validator.evaluate(champ, chall)
    assert res_bad.decision == "REJECT"
    assert res_bad.scorecard["has_severe_loss"] is True
