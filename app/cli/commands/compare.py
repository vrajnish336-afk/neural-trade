import argparse
from app.services.observability import ObservabilityService
from app.research.comparator import CrossExperimentComparator
from app.research.evidence import ResearchEvidenceEvaluator

def setup_compare_parser(subparsers):
    parser = subparsers.add_parser("compare", help="Safely compare two research experiments")
    parser.add_argument("run_id_1", help="The ID of the first experiment")
    parser.add_argument("run_id_2", help="The ID of the second experiment")
    parser.set_defaults(func=run_compare)

def run_compare(args: argparse.Namespace) -> int:
    exp1 = ObservabilityService.get_experiment(args.run_id_1)
    exp2 = ObservabilityService.get_experiment(args.run_id_2)
    
    if not exp1:
        print(f"Error: Experiment not found for ID '{args.run_id_1}'")
        return 1
        
    if not exp2:
        print(f"Error: Experiment not found for ID '{args.run_id_2}'")
        return 1
        
    print("=== RESEARCH EVIDENCE COMPARISON ===")
    
    comparator = CrossExperimentComparator()
    report = comparator.compare(exp1, exp2)
    
    # Also grab their evidence status
    evaluator = ResearchEvidenceEvaluator()
    ev1 = evaluator.evaluate(exp1)
    ev2 = evaluator.evaluate(exp2)
    
    print("\n[ EXPERIMENT A ]")
    print(f"ID: {report.exp1_id}")
    print(f"Dataset: {report.dataset_1}")
    print(f"Symbol: {report.symbol_1}")
    print(f"Timeframe: {report.timeframe_1}")
    print(f"Seed: {report.seed_1}")
    print(f"Strategy: {report.strategy_1}")
    print(f"Evidence Status: {ev1.status.value} ({ev1.conclusion.value})")
    print(f"OOS Trades: {report.oos_trades_1}")
    print(f"OOS Net PnL: {report.oos_pnl_1}")
    print(f"OOS PF: {report.oos_pf_1}")
    
    print("\n[ EXPERIMENT B ]")
    print(f"ID: {report.exp2_id}")
    print(f"Dataset: {report.dataset_2}")
    print(f"Symbol: {report.symbol_2}")
    print(f"Timeframe: {report.timeframe_2}")
    print(f"Seed: {report.seed_2}")
    print(f"Strategy: {report.strategy_2}")
    print(f"Evidence Status: {ev2.status.value} ({ev2.conclusion.value})")
    print(f"OOS Trades: {report.oos_trades_2}")
    print(f"OOS Net PnL: {report.oos_pnl_2}")
    print(f"OOS PF: {report.oos_pf_2}")
    
    print("\n[ DIFFERENCES ]")
    if not report.differences:
        print("None (Identical core conditions)")
    else:
        for diff in report.differences:
            print(f"- {diff}")
            
    print(f"\n[ COMPARABILITY ]\n{report.comparability.value}")
    
    print(f"\n[ CONCLUSION ]\n{report.conclusion}")
    
    return 0
