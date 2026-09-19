import json
import logging
from typing import Dict, Any, List
from app.database.schema import init_db
from app.research.dataset import generate_synthetic_data
from app.research.splits import split_research_windows
from app.backtesting.models import CostConfig
from app.backtesting.engine import BacktestEngine
from app.research.robustness.runner import create_engine_factory
from app.diagnostics.telemetry import telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

def run_variant(train_bars, val_bars, test_bars, use_adaptive: bool, disable_regime_switching: bool = False) -> Dict[str, Any]:
    telemetry.reset()
    telemetry.enabled = True
    engine = create_engine_factory(use_adaptive=use_adaptive)
    
    if use_adaptive and disable_regime_switching and engine.ensemble.adaptive:
        engine.ensemble.adaptive.disable_regime_switching = True
        
    # 1. Train
    res_train = engine.run(train_bars)
    
    # 2. Validation
    res_val = engine.run(val_bars)
    
    # 3. Test
    res_test = engine.run(test_bars)
    
    return {
        "train": {"trades": res_train.number_of_trades, "return_pct": res_train.total_return_pct, "win_rate": res_train.win_rate},
        "val": {"trades": res_val.number_of_trades, "return_pct": res_val.total_return_pct, "win_rate": res_val.win_rate},
        "test": {"trades": res_test.number_of_trades, "return_pct": res_test.total_return_pct, "win_rate": res_test.win_rate}
    }

if __name__ == "__main__":
    init_db()
    print("==============================================")
    print(" SIGNAL QUALITY EXPERIMENT (PHASE 11)")
    print("==============================================")
    
    seeds = [101, 202, 303, 404, 505]
    results = {"BASELINE": [], "SCORE_AWARE": [], "REGIME_AWARE": []}
    
    for s in seeds:
        print(f"\nEvaluating Seed {s}...")
        bars = generate_synthetic_data(["TEST"], num_bars=2000, seed=s)["TEST"]
        train_b, val_b, test_b, _, _, _ = split_research_windows(bars, train_pct=0.5, val_pct=0.25, test_pct=0.25)
        
        # A. Baseline
        base = run_variant(train_b, val_b, test_b, use_adaptive=False)
        results["BASELINE"].append(base)
        print(f"  BASELINE     | Train: {base['train']['return_pct']:.2f}% | Val: {base['val']['return_pct']:.2f}% | Test: {base['test']['return_pct']:.2f}%")
        
        # B. Score-Aware Filter (Uses adaptive to calculate score but limits strategy shifting)
        score_aware = run_variant(train_b, val_b, test_b, use_adaptive=True, disable_regime_switching=True) 
        results["SCORE_AWARE"].append(score_aware)
        print(f"  SCORE_AWARE  | Train: {score_aware['train']['return_pct']:.2f}% | Val: {score_aware['val']['return_pct']:.2f}% | Test: {score_aware['test']['return_pct']:.2f}%")
        
        # C. Regime-Aware (Fully adaptive system)
        regime_aware = run_variant(train_b, val_b, test_b, use_adaptive=True, disable_regime_switching=False)
        results["REGIME_AWARE"].append(regime_aware)
        print(f"  REGIME_AWARE | Train: {regime_aware['train']['return_pct']:.2f}% | Val: {regime_aware['val']['return_pct']:.2f}% | Test: {regime_aware['test']['return_pct']:.2f}%")

    with open("reports/phase11_filter_experiment.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nExperiment diagnostics persisted to reports/phase11_filter_experiment.json")
