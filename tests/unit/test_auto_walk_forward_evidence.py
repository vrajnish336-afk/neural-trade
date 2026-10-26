import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.research.robustness.walk_forward import (
    run_walk_forward_robustness,
    attach_evidence_to_experiment,
    WalkForwardResultSet
)
from app.research.robustness.artifact import (
    load_evidence_artifact,
    build_evidence_artifact,
    FoldBoundary,
    FoldEvidenceMetrics,
    AggregateEvidenceMetrics
)
from app.research.challenger import ChampionChallengerValidator
from app.research.models import ResearchExperiment
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics

def _create_deterministic_bars(count=20):
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bars = []
    price = 100.0
    for i in range(count):
        # Create varying price trajectory to trigger indicator changes
        price += (1.5 if i % 2 == 0 else -0.8)
        bars.append(MarketBar(
            symbol="BTC_TEST",
            timestamp=base_time + timedelta(hours=i),
            open=price - 0.5,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=1000.0
        ))
    return bars

def _create_engine_factory():
    def factory():
        ensemble = StrategyEnsemble([TrendFollowingStrategy()])
        risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0), risk_per_trade_pct=0.05)
        return BacktestEngine(
            ensemble=ensemble,
            risk_engine=risk_engine,
            initial_capital=10000.0,
            cost_config=CostConfig(commission_rate=0.001, slippage_rate=0.001)
        )
    return factory

def _create_mock_analytics_report(exp_id: str, ret_pct: float, dd_pct: float, trades: int, pf: float = 1.6):
    wins = int(trades * 0.6)
    losses = trades - wins
    return FullAnalyticsReport(
        backtest_id=exp_id,
        trade_metrics=TradeMetrics(
            total_trades=trades, winning_trades=wins, losing_trades=losses,
            win_rate=(wins / trades * 100.0) if trades > 0 else 0.0,
            gross_pnl=ret_pct * 10.0, net_pnl=ret_pct * 10.0, total_commission=0.0, total_slippage=0.0,
            profit_factor=pf, max_consecutive_losses=2,
            average_pnl=(ret_pct * 10.0) / trades if trades > 0 else 0.0,
            average_win=2.0, average_loss=-1.0, largest_win=4.0, largest_loss=-2.0,
            max_consecutive_wins=3, average_holding_hours=12.0
        ),
        equity_metrics=EquityMetrics(
            initial_capital=10000.0, final_equity=10000.0 * (1.0 + ret_pct / 100.0),
            total_return_pct=ret_pct, max_drawdown_pct=dd_pct, average_drawdown_pct=dd_pct / 2.0,
            absolute_pnl=10000.0 * (ret_pct / 100.0), max_drawdown_amount=10000.0 * (dd_pct / 100.0),
            time_in_drawdown_pct=10.0, recovery_periods=2
        ),
        strategy_attribution=[], regime_attribution=[], signal_bucket_attribution=[],
        intelligence_attribution=[], failure_findings=[], strategy_comparisons=[]
    )

def test_successful_run_generates_and_persists_evidence():
    bars = _create_deterministic_bars(20)
    engine_factory = _create_engine_factory()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_research.sqlite")
        json_path = os.path.join(tmpdir, "test_artifact.json")

        results = run_walk_forward_robustness(
            bars=bars,
            engine_factory=engine_factory,
            window_size=8,
            step_size=4,
            candidate_id="cand_alpha",
            strategy_name="TrendFollowing",
            parameters={"lookback": 14},
            config_snapshot={"cost_model": "slippage_0.001"},
            auto_persist=True,
            db_path=db_path,
            json_path=json_path
        )

        assert isinstance(results, WalkForwardResultSet)
        assert len(results) > 0
        assert results.persistence_success is True
        assert results.persistence_failed is False
        assert results.persistence_error is None

        # Verify artifact contents
        art = results.artifact
        assert art is not None
        assert art.candidate_id == "cand_alpha"
        assert art.strategy_name == "TrendFollowing"
        assert art.parameters == {"lookback": 14}
        assert art.dataset_fingerprint != ""
        assert art.code_revision != ""
        assert len(art.folds) == len(results)
        assert art.reconciled is True

        # Verify aggregate reconciliation with fold sums
        assert sum(f.trades for f in art.folds) == art.aggregate.total_trades
        assert sum(f.wins for f in art.folds) == art.aggregate.wins
        assert sum(f.losses for f in art.folds) == art.aggregate.losses
        assert abs(sum(f.gross_profit for f in art.folds) - art.aggregate.gross_profit) < 1e-2
        assert abs(sum(f.gross_loss for f in art.folds) - art.aggregate.gross_loss) < 1e-2
        assert abs(sum(f.net_pnl for f in art.folds) - art.aggregate.net_pnl) < 1e-2
        assert abs(sum(f.total_costs for f in art.folds) - art.aggregate.total_costs) < 1e-2

        # Verify persistence in SQLite
        loaded = load_evidence_artifact(art.artifact_id, db_path=db_path)
        assert loaded is not None
        assert loaded.artifact_id == art.artifact_id
        assert loaded.candidate_id == "cand_alpha"
        assert os.path.exists(json_path)

        # Gate promotion integration with champion
        champ_rep = _create_mock_analytics_report("champ", ret_pct=10.0, dd_pct=5.0, trades=50, pf=1.4)
        chall_rep = _create_mock_analytics_report("chall", ret_pct=18.0, dd_pct=4.5, trades=60, pf=1.8)

        champ = ResearchExperiment(
            experiment_id="champ", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
            strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
            created_at=datetime.now(timezone.utc), status="COMPLETED",
            validation_results=[], out_of_sample_report=champ_rep
        )
        chall = ResearchExperiment(
            experiment_id="chall", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
            strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
            created_at=datetime.now(timezone.utc), status="COMPLETED",
            validation_results=[], out_of_sample_report=chall_rep
        )
        attach_evidence_to_experiment(chall, results)

        validator = ChampionChallengerValidator(db_path=db_path, require_persisted_evidence=True)
        eval_res = validator.evaluate(champ, chall)
        assert eval_res.decision == "PROMOTE"
        assert eval_res.scorecard["has_fold_evidence"] is True
        assert eval_res.scorecard["persistence_failed"] is False

def test_missing_data_blocks_promotion():
    # Only 3 bars with window_size 10 -> 0 folds formed
    insufficient_bars = _create_deterministic_bars(3)
    engine_factory = _create_engine_factory()

    results = run_walk_forward_robustness(
        bars=insufficient_bars,
        engine_factory=engine_factory,
        window_size=10,
        step_size=5
    )

    assert len(results) == 0
    assert results.artifact is None
    assert results.persistence_success is False
    assert "Missing data" in results.persistence_error

    # Gate evaluation: candidate with missing evidence must NEVER be promoted
    champ_rep = _create_mock_analytics_report("champ", ret_pct=10.0, dd_pct=5.0, trades=50)
    chall_rep = _create_mock_analytics_report("chall", ret_pct=25.0, dd_pct=3.0, trades=60)

    champ = ResearchExperiment(
        experiment_id="champ", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=champ_rep
    )
    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep
    )
    attach_evidence_to_experiment(chall, results)

    validator = ChampionChallengerValidator()
    eval_res = validator.evaluate(champ, chall)
    assert eval_res.decision == "INCONCLUSIVE"
    assert "Missing Walk-Forward Fold Evidence" in eval_res.decision_reasons
    assert eval_res.decision != "PROMOTE"

def test_persistence_failure_blocks_promotion():
    bars = _create_deterministic_bars(16)
    engine_factory = _create_engine_factory()

    # Pass an impossible DB path (directory doesn't exist and cannot be opened directly)
    invalid_db_path = "/nonexistent_folder_abc_xyz/db.sqlite"

    results = run_walk_forward_robustness(
        bars=bars,
        engine_factory=engine_factory,
        window_size=8,
        step_size=4,
        auto_persist=True,
        db_path=invalid_db_path
    )

    assert len(results) > 0
    assert results.persistence_success is False
    assert results.persistence_failed is True
    assert results.persistence_error is not None

    champ_rep = _create_mock_analytics_report("champ", ret_pct=10.0, dd_pct=5.0, trades=50)
    chall_rep = _create_mock_analytics_report("chall", ret_pct=25.0, dd_pct=3.0, trades=60)

    champ = ResearchExperiment(
        experiment_id="champ", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=champ_rep
    )
    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep
    )
    attach_evidence_to_experiment(chall, results)
    assert chall.persistence_failed is True

    validator = ChampionChallengerValidator()
    eval_res = validator.evaluate(champ, chall)
    assert eval_res.decision == "INCONCLUSIVE"
    assert "Walk-Forward Evidence Persistence Failed" in eval_res.decision_reasons
    assert eval_res.scorecard["persistence_failed"] is True
    assert eval_res.decision != "PROMOTE"

def test_missing_database_record_blocks_promotion():
    # Candidate specifies an artifact_id, but the record is not in SQLite
    champ_rep = _create_mock_analytics_report("champ", ret_pct=10.0, dd_pct=5.0, trades=50)
    chall_rep = _create_mock_analytics_report("chall", ret_pct=25.0, dd_pct=3.0, trades=60)

    champ = ResearchExperiment(
        experiment_id="champ", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=champ_rep
    )
    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep,
        artifact_id="nonexistent_artifact_123"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "empty.sqlite")
        validator = ChampionChallengerValidator(db_path=db_path)
        eval_res = validator.evaluate(champ, chall)
        assert eval_res.decision == "INCONCLUSIVE"
        assert any("Persistence Record Missing" in r for r in eval_res.decision_reasons)
        assert eval_res.decision != "PROMOTE"

def test_reconciliation_mismatch_blocks_promotion():
    champ_rep = _create_mock_analytics_report("champ", ret_pct=10.0, dd_pct=5.0, trades=50)
    chall_rep = _create_mock_analytics_report("chall", ret_pct=25.0, dd_pct=3.0, trades=60)

    champ = ResearchExperiment(
        experiment_id="champ", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=champ_rep
    )
    chall = ResearchExperiment(
        experiment_id="chall", dataset_id="d1", symbols=["BTC_TEST"], timeframe="1h",
        strategy="Strat", configuration="c", starting_capital=10000.0, random_seed=42,
        created_at=datetime.now(timezone.utc), status="COMPLETED",
        validation_results=[], out_of_sample_report=chall_rep
    )

    # Artificially create an unreconciled artifact object
    boundaries = FoldBoundary(
        train_start="t1", train_end="t2", validation_start="v1",
        validation_end="v2", test_start="s1", test_end="s2"
    )
    f1 = FoldEvidenceMetrics(
        window_id=1, boundaries=boundaries, trades=20, wins=12, losses=8,
        profit_factor=1.5, expectancy=1.0, max_drawdown_pct=2.0,
        gross_profit=30.0, gross_loss=20.0, net_pnl=10.0, total_costs=2.0
    )
    agg = AggregateEvidenceMetrics(
        total_trades=20, wins=12, losses=8, profit_factor=1.5, expectancy=1.0,
        max_drawdown_pct=2.0, gross_profit=30.0, gross_loss=20.0, net_pnl=10.0, total_costs=2.0
    )
    art = build_evidence_artifact("chall", "Strat", {}, "fp", [f1], agg)
    art.reconciled = False # simulate corrupted/tampered artifact

    chall.walk_forward_artifact = art

    validator = ChampionChallengerValidator()
    eval_res = validator.evaluate(champ, chall)
    assert eval_res.decision == "INCONCLUSIVE"
    assert "Walk-Forward Evidence Reconciliation Mismatch" in eval_res.decision_reasons
    assert eval_res.decision != "PROMOTE"
