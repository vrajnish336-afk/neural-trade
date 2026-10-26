import json
import logging
from datetime import datetime, timezone

from app.config import config
from app.database.schema import init_db
from app.data.csv_provider import CsvHistoricalDataProvider
from app.backtesting.models import CostConfig
from app.research.robustness.runner import create_engine_factory
from app.research.robustness.walk_forward import (
    run_walk_forward_robustness,
    attach_evidence_to_experiment
)
from app.research.robustness.artifact import (
    load_evidence_artifact,
    load_evidence_from_json,
    verify_artifact_reconciliation
)
from app.research.challenger import ChampionChallengerValidator
from app.research.models import ResearchExperiment
from app.analytics.engine import generate_analytics_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("smoke_run")

def run_smoke():
    init_db()
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False

    provider = CsvHistoricalDataProvider("data/historical")
    all_bars = []
    
    # 1. Dataset Boundary Verification: Strictly first 50% (Train/Validation only)
    for sym in ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT"]:
        for tf in ["1H"]:
            b = provider.get_historical_bars(sym, tf, datetime(2010, 1, 1, tzinfo=timezone.utc))
            b.sort(key=lambda x: x.timestamp)
            half = int(len(b) * 0.5)
            train_val_slice = b[:half]
            holdout_start = b[half].timestamp if half < len(b) else None
            train_val_end = train_val_slice[-1].timestamp if train_val_slice else None
            logger.info(f"{sym}: Total={len(b)}, Train/Val={len(train_val_slice)} (End: {train_val_end}), Holdout Start: {holdout_start}")
            all_bars.extend(train_val_slice)
            
    all_bars.sort(key=lambda x: x.timestamp)
    logger.info(f"Aggregated Train/Validation Bars: {len(all_bars)} (From {all_bars[0].timestamp} to {all_bars[-1].timestamp})")

    # 2. Fixed Configuration Engine Factory
    def engine_factory():
        eng = create_engine_factory(use_adaptive=True, breakout_period=20)
        eng.cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.001)
        return eng

    # 3. Perform Exactly One Governed Walk-Forward Smoke Run
    json_path = "reports/smoke_walk_forward_artifact.json"
    results = run_walk_forward_robustness(
        bars=all_bars,
        engine_factory=engine_factory,
        window_size=2000,
        step_size=2000,
        candidate_id="smoke_run_baseline_50",
        strategy_name="AdaptiveEnsemble",
        parameters={"min_score": 50.0, "breakout_period": 20},
        config_snapshot={
            "cost_config": {"commission": 0.001, "slippage": 0.001},
            "paper_trading": True,
            "live_trading": False
        },
        auto_persist=True,
        json_path=json_path
    )

    art = results.artifact
    if not art:
        print("BLOCKED: Artifact was not generated.")
        return

    # 4. Verify Persistence
    db_art = load_evidence_artifact(art.artifact_id)
    json_art = load_evidence_from_json(json_path)

    assert db_art is not None, "Failed to load artifact from SQLite DB"
    assert json_art is not None, "Failed to load artifact from JSON"
    assert db_art.artifact_id == art.artifact_id

    # 5. Verify Reconciliation
    is_rec, issues = verify_artifact_reconciliation(db_art)
    assert is_rec, f"Reconciliation issues: {issues}"

    # Print Fold Breakdown
    print("\n--- SMOKE RUN ARTIFACT VERIFICATION ---")
    print(f"Artifact ID: {art.artifact_id}")
    print(f"Candidate:   {art.candidate_id}")
    print(f"Fingerprint: {art.dataset_fingerprint[:16]}...")
    print(f"Revision:    {art.code_revision[:10]}")
    print(f"Folds Count: {len(art.folds)}")
    print(f"Aggregate:   Trades={art.aggregate.total_trades}, Wins={art.aggregate.wins}, Losses={art.aggregate.losses}, PF={art.aggregate.profit_factor:.2f}, NetPnL=${art.aggregate.net_pnl:.2f}, Costs=${art.aggregate.total_costs:.2f}")

    for f in art.folds:
        print(f"  Fold {f.window_id}: Trades={f.trades} (W={f.wins} L={f.losses}), PF={f.profit_factor:.2f}, NetPnL=${f.net_pnl:.2f}, Costs=${f.total_costs:.2f}, Exp=${f.expectancy:.2f}")

    # 6. Candidate Gate Evaluation Check
    # Build candidate ResearchExperiment
    chall_rep = generate_analytics_report(
        "smoke_chall",
        engine_factory().run(all_bars[-500:]) # arbitrary test split for gate formatting
    )
    chall = ResearchExperiment(
        experiment_id="smoke_chall",
        dataset_id="train_val_historical",
        symbols=["BTC_USDT"],
        timeframe="1h",
        strategy="AdaptiveEnsemble",
        configuration="fixed_smoke",
        starting_capital=10000.0,
        random_seed=42,
        created_at=datetime.now(timezone.utc),
        status="COMPLETED",
        validation_results=[],
        out_of_sample_report=chall_rep
    )
    attach_evidence_to_experiment(chall, results)

    # Champion baseline
    champ_rep = generate_analytics_report(
        "smoke_champ",
        engine_factory().run(all_bars[-500:])
    )
    champ = ResearchExperiment(
        experiment_id="smoke_champ",
        dataset_id="train_val_historical",
        symbols=["BTC_USDT"],
        timeframe="1h",
        strategy="AdaptiveEnsemble",
        configuration="fixed_smoke",
        starting_capital=10000.0,
        random_seed=42,
        created_at=datetime.now(timezone.utc),
        status="COMPLETED",
        validation_results=[],
        out_of_sample_report=champ_rep
    )

    validator = ChampionChallengerValidator(require_persisted_evidence=True)
    gate_res = validator.evaluate(champ, chall)

    print("\n--- CANDIDATE GATE EVALUATION ---")
    print(f"Gate Decision:          {gate_res.decision}")
    print(f"Reasons:                {gate_res.decision_reasons}")
    print(f"Has Fold Evidence:      {gate_res.scorecard.get('has_fold_evidence')}")
    print(f"Persistence Verified:   {not gate_res.scorecard.get('persistence_failed')}")
    print(f"Has Severe Loss:        {gate_res.scorecard.get('has_severe_loss')}")

if __name__ == "__main__":
    run_smoke()
