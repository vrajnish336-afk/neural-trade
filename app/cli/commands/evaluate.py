import argparse
from app.services.observability import ObservabilityService
from app.research.evidence import ResearchEvidenceEvaluator

def setup_evaluate_parser(subparsers):
    parser = subparsers.add_parser("evaluate", help="Evaluate the research evidence of an experiment")
    parser.add_argument("run_id", help="The ID of the experiment to evaluate")
    parser.set_defaults(func=run_evaluate)

def run_evaluate(args: argparse.Namespace) -> int:
    # We retrieve it via ObservabilityService.get_experiment since run_id is an experiment_id
    experiment = ObservabilityService.get_experiment(args.run_id)
    
    if not experiment:
        print(f"Error: Experiment not found for ID '{args.run_id}'")
        return 1
        
    evaluator = ResearchEvidenceEvaluator()
    summary = evaluator.evaluate(experiment)
    
    print("=== RESEARCH EVIDENCE EVALUATION ===")
    print(f"\nRun: {experiment.experiment_id}")
    print(f"Strategy: {experiment.strategy}")
    print(f"Dataset: {experiment.dataset_id}")
    print(f"Seed: {experiment.random_seed}\n")
    
    print("DATA COVERAGE")
    print("-------------")
    print(f"Train: {summary.data_coverage.train}")
    print(f"Validation: {summary.data_coverage.validation}")
    print(f"OOS: {summary.data_coverage.oos}\n")
    
    print("ROBUSTNESS")
    print("----------")
    print(f"Walk-forward: {summary.robustness.walk_forward.value}")
    print(f"Multi-seed: {summary.robustness.multi_seed.value}")
    print(f"Cost/Slippage Stress: {summary.robustness.cost_slippage_stress.value}\n")
    
    print("SAMPLE SIZE")
    print("-----------")
    print(f"Total trades: {summary.sample_size_eval.total_trades}")
    print(f"OOS trades: {summary.sample_size_eval.oos_trades}")
    print(f"Standard: {summary.sample_size_eval.standard}")
    print(f"Assessment: {summary.sample_size_eval.assessment}")
    if summary.sample_size_eval.regime_trades:
        print("Regime evidence:")
        for r_name, r_trades in summary.sample_size_eval.regime_trades.items():
            trade_text = str(r_trades) if r_trades > 0 else "NO TRADE EVIDENCE"
            print(f"  - {r_name}: {trade_text}")
    print("")
            
    print("PERFORMANCE")
    print("-----------")
    perf = summary.performance
    print(f"OOS Net PnL: {perf.oos_net_pnl if perf.oos_net_pnl is not None else 'NOT_AVAILABLE'}")
    print(f"OOS Profit Factor: {perf.oos_profit_factor if perf.oos_profit_factor is not None else 'NOT_AVAILABLE'}")
    print(f"OOS Win Rate: {perf.oos_win_rate if perf.oos_win_rate is not None else 'NOT_AVAILABLE'}")
    print(f"Degradation: {perf.degradation_note}\n")
    
    print("EVIDENCE")
    print("--------")
    print(f"Status: {summary.status.value}\n")
    if summary.reasons:
        print("Reasons:")
        for r in summary.reasons:
            print(f"- {r}")
    print("")
            
    print("LIMITATIONS")
    print("-----------")
    for l in summary.limitations:
        print(f"- {l}")
    print(f"\n* Note: {summary.statistical_significance_note}\n")
        
    print("CONCLUSION")
    print("----------")
    print(summary.conclusion.value)
    
    return 0
