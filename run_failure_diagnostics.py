import json
import logging
from app.database.schema import init_db
from app.research.dataset import generate_regime_dataset
from app.research.robustness.runner import create_engine_factory
from app.diagnostics.telemetry import telemetry
from app.analysis.failure_diagnostics import FailureDiagnosticEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

if __name__ == "__main__":
    init_db()
    print("==============================================")
    print(" FAILURE DIAGNOSTICS (PHASE 11)")
    print("==============================================")
    
    # 1. Run backtests across all regimes to generate telemetry + closed trades
    regimes = ["TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY", "LOW_VOLATILITY"]
    all_trades = []
    
    telemetry.reset()
    telemetry.enabled = True
    
    for r in regimes:
        print(f"Generating and evaluating {r}...")
        bars = generate_regime_dataset(r, num_bars=1000)
        engine = create_engine_factory(use_adaptive=True)
        engine.run(bars)
        all_trades.extend(engine.closed_trades)
        
    engine_diag = FailureDiagnosticEngine(all_trades)
    
    # 2. Extract Regime Failure Matrix
    print("\n--- REGIME FAILURE MATRIX ---")
    regime_matrix = engine_diag.get_regime_failure_matrix()
    for row in regime_matrix:
        print(f"{row['strategy']:15s} | {row['regime']:15s} | Trades: {row['sample_count']:3d} | Win Rate: {row['win_rate']:5.2f}% | PF: {row['profit_factor']:5.2f} | {row['quality_status']}")
        
    # 3. Signal Score Analysis
    print("\n--- SIGNAL SCORE ANALYSIS ---")
    score_analysis = engine_diag.get_signal_score_analysis()
    for row in score_analysis:
        print(f"Bucket: {row['score_bucket']:6s} | Trades: {row['trade_count']:3d} | Win Rate: {row['win_rate']:5.2f}% | PF: {row['profit_factor']:5.2f}")
        
    # 4. TRENDING_UP Diagnostics
    print("\n--- TRENDING_UP DIAGNOSTICS ---")
    tu_diag = engine_diag.diagnose_trending_up()
    print(json.dumps(tu_diag, indent=2))
    
    # 5. Rejection Funnel By Regime
    print("\n--- REJECTION FUNNEL BY REGIME ---")
    rejection_funnel = {}
    for regime, reasons in telemetry.regime_rejections.items():
        rejection_funnel[regime] = {str(k.name): v for k, v in reasons.items() if v > 0}
        
    for r, reasons in rejection_funnel.items():
        print(f"\n{r}:")
        for reason, count in reasons.items():
            print(f"  {reason}: {count}")
            
    # Export results
    results = {
        "regime_matrix": regime_matrix,
        "score_analysis": score_analysis,
        "trending_up_diagnostics": tu_diag,
        "rejection_funnel": rejection_funnel
    }
    
    with open("reports/phase11_diagnostics.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nDetailed diagnostics persisted to reports/phase11_diagnostics.json")
