import os
import sqlite3
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
    load_evidence_from_json,
    save_evidence_artifact
)
from app.research.challenger import ChampionChallengerValidator
from app.research.models import ResearchExperiment
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics

def _create_deterministic_bars(count=20):
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bars = []
    price = 100.0
    for i in range(count):
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

def test_e2e_runner_to_sqlite_json_to_gate_success():
    """Verify complete flow: runner -> SQLite/JSON storage -> gate promotion."""
    bars = _create_deterministic_bars(24)
    engine_factory = _create_engine_factory()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "e2e_pipeline.sqlite")
        json_path = os.path.join(tmpdir, "e2e_artifact.json")

        results = run_walk_forward_robustness(
            bars=bars,
            engine_factory=engine_factory,
            window_size=8,
            step_size=4,
            candidate_id="cand_e2e_01",
            strategy_name="TrendFollowing",
            parameters={"lookback": 14},
            config_snapshot={"cost_model": "slippage_0.001"},
            auto_persist=True,
            db_path=db_path,
            json_path=json_path
        )

        assert results.persistence_success is True
        art = results.artifact
        assert art is not None

        # Verify load from SQLite
        db_art = load_evidence_artifact(art.artifact_id, db_path=db_path)
        assert db_art is not None
        assert db_art.artifact_id == art.artifact_id
        assert db_art.reconciled is True

        # Verify load from JSON
        json_art = load_evidence_from_json(json_path)
        assert json_art is not None
        assert json_art.artifact_id == art.artifact_id
        assert json_art.reconciled is True

        # Candidate gate evaluation
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

def test_e2e_corrupted_sqlite_payload_blocks_promotion():
    """Verify corrupted JSON payload stored in SQLite blocks promotion."""
    bars = _create_deterministic_bars(20)
    engine_factory = _create_engine_factory()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "corrupted_pipeline.sqlite")

        results = run_walk_forward_robustness(
            bars=bars,
            engine_factory=engine_factory,
            window_size=8,
            step_size=4,
            candidate_id="cand_corrupted",
            auto_persist=True,
            db_path=db_path
        )
        art_id = results.artifact.artifact_id

        # Intentionally corrupt the database payload
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE walk_forward_evidence SET artifact_json = 'INVALID_JSON_CORRUPTED' WHERE artifact_id = ?", (art_id,))
        conn.commit()
        conn.close()

        # Loading corrupted artifact returns None safely
        loaded = load_evidence_artifact(art_id, db_path=db_path)
        assert loaded is None

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
            artifact_id=art_id
        )

        validator = ChampionChallengerValidator(db_path=db_path, require_persisted_evidence=True)
        eval_res = validator.evaluate(champ, chall)
        assert eval_res.decision == "INCONCLUSIVE"
        assert any("Persistence Record Missing" in r for r in eval_res.decision_reasons)
        assert eval_res.decision != "PROMOTE"

def test_e2e_tampered_storage_metrics_blocks_promotion():
    """Verify tampered fold metrics in storage that violate reconciliation block promotion."""
    bars = _create_deterministic_bars(20)
    engine_factory = _create_engine_factory()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "tampered_pipeline.sqlite")

        results = run_walk_forward_robustness(
            bars=bars,
            engine_factory=engine_factory,
            window_size=8,
            step_size=4,
            candidate_id="cand_tampered",
            auto_persist=True,
            db_path=db_path
        )
        art = results.artifact

        # Tamper with the JSON payload by modifying total_trades in aggregate
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT artifact_json FROM walk_forward_evidence WHERE artifact_id = ?", (art.artifact_id,))
        raw_json = cursor.fetchone()[0]

        import json
        data = json.loads(raw_json)
        # Artificially modify aggregate total_trades to mismatch sum of folds
        data["aggregate"]["total_trades"] = data["aggregate"]["total_trades"] + 100
        tampered_json = json.dumps(data)

        conn.execute("UPDATE walk_forward_evidence SET artifact_json = ? WHERE artifact_id = ?", (tampered_json, art.artifact_id))
        conn.commit()
        conn.close()

        # Loading tampered artifact flags reconciled as False
        loaded = load_evidence_artifact(art.artifact_id, db_path=db_path)
        assert loaded is not None
        assert loaded.reconciled is False

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
            walk_forward_artifact=loaded
        )

        validator = ChampionChallengerValidator(db_path=db_path)
        eval_res = validator.evaluate(champ, chall)
        assert eval_res.decision == "INCONCLUSIVE"
        assert "Walk-Forward Evidence Reconciliation Mismatch" in eval_res.decision_reasons
        assert eval_res.decision != "PROMOTE"

def test_e2e_corrupted_json_file_handling():
    """Verify corrupted JSON file handling in load_evidence_from_json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "corrupted.json")
        with open(json_path, "w") as f:
            f.write("{{malformed_json_content")

        loaded = load_evidence_from_json(json_path)
        assert loaded is None
