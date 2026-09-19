import json
import logging
from app.database.schema import init_db
from app.research.robustness.runner import run_full_robustness_experiment

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

if __name__ == "__main__":
    init_db()
    print("==============================================")
    print(" ROBUSTNESS & STATISTICAL VALIDATION (PHASE 10)")
    print("==============================================")
    
    print("Running comprehensive robustness framework. This will perform Monte Carlo resampling, cross-seed validation, walk-forward windows, parameter grids, and transaction cost stress testing...")
    
    results = run_full_robustness_experiment()
    
    scorecard = results["scorecard"]
    
    print("\n================ ROBUSTNESS SCORECARD ================")
    print(f"Overall Status:        {scorecard['overall_status']}")
    print(f"Cross-Seed Stability:  {scorecard['cross_seed_stability']}")
    print(f"Cost Resilience:       {scorecard['cost_resilience']}")
    print(f"Monte Carlo Stability: {scorecard['monte_carlo_stability']}")
    print(f"Sample Size Adequacy:  {scorecard['sample_size_adequacy']}")
    
    print("\n--- MONTE CARLO (1000 resamples) ---")
    mc = results["monte_carlo"]
    print(f"Median Return: {mc['median_return_pct']:.2f}%")
    print(f"5th %ile Return: {mc['p05_return_pct']:.2f}%")
    print(f"95th %ile Return: {mc['p95_return_pct']:.2f}%")
    
    print("\n--- TRANSACTION COST STRESS ---")
    for c in results["cost_stress"]:
        print(f"Multiplier: {c['multiplier']}x | Trades: {c['total_trades']} | Return: {c['return_pct']:.2f}% | Degradation: {c['degradation_pct']:.2f}%")
        
    print("\n--- SEED ROBUSTNESS ---")
    for s in results["seed_robustness"]:
        print(f"Seed: {s['seed']} | Trades: {s['trades']} | Return: {s['return_pct']:.2f}%")
        
    print("\n--- REGIME ROBUSTNESS ---")
    for reg, vals in results["regimes"].items():
        print(f"{reg:16s} | Trades: {vals['trades']:3d} | Return: {vals['return_pct']:7.2f}% | Win Rate: {vals['win_rate']:.2f}%")
        
    with open("reports/phase10_robustness.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nDetailed diagnostics persisted to reports/phase10_robustness.json")
