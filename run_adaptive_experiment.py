import logging
import json
from app.database.schema import init_db
from app.research.dataset import generate_synthetic_data
from app.backtesting.models import CostConfig
from app.diagnostics.telemetry import telemetry
from app.diagnostics.adaptive_walk_forward import run_adaptive_calibration_experiment

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

if __name__ == "__main__":
    init_db()
    print("==============================================")
    print(" ADAPTIVE STRATEGY INTELLIGENCE (PHASE 9)")
    print("==============================================")
    
    # 1. Dataset Generation
    print("Generating Chronological Dataset (2000 bars)...")
    bars = generate_synthetic_data(["SYNC_BTC"], num_bars=2000, seed=42)["SYNC_BTC"]
    
    # 2. Walk-Forward / Adaptive Calibration
    print("\nRunning Baseline vs. Adaptive Ensemble...")
    results = run_adaptive_calibration_experiment(bars, CostConfig())
    
    print("\n--- CONTROLLED CALIBRATION EXPERIMENT ---")
    base = results["BASELINE"]
    print(f"BASELINE  -> Trades: {base['trades']:3d} | Return: {base['return_pct']:7.2f}% | Win Rate: {base['win_rate']:5.2f}% | PF: {base['profit_factor']:.2f}")
    
    adapt = results["ADAPTIVE"]
    print(f"ADAPTIVE  -> Trades: {adapt['trades']:3d} | Return: {adapt['return_pct']:7.2f}% | Win Rate: {adapt['win_rate']:5.2f}% | PF: {adapt['profit_factor']:.2f}")
    
    print("\n--- ADAPTIVE DIAGNOSTICS ---")
    print(f"Strategy Switches (Anti-Churn): {adapt['strategy_switches']}")
    print(f"Decisions w/ HIGH_CONFIDENCE:   {adapt['decisions_high_conf']}")
    print(f"Decisions w/ LOW_CONFIDENCE:    {adapt['decisions_low_conf']}")
    print(f"Decisions w/ INSUFF_EVIDENCE:   {adapt['decisions_insufficient']}")
    
    # 3. Export
    with open("reports/phase9_adaptive.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nDetailed diagnostics persisted to reports/phase9_adaptive.json")
