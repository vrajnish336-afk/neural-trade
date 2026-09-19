import argparse
from app.research.experiment_intelligence.service import ExperimentComparisonService

def setup_experiment_parser(subparsers):
    p = subparsers.add_parser("experiment-compare", help="Compare two experiments")
    p.add_argument("id1", help="First experiment ID")
    p.add_argument("id2", help="Second experiment ID")
    p.set_defaults(func=run_compare)
    
def _print_safety_banner():
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("EXPERIMENT COMPARISON IS RESEARCH EVIDENCE ANALYSIS.")
    print("NO AUTOMATIC STRATEGY DEPLOYMENT.")
    print("==================================================\n")

def run_compare(args) -> int:
    _print_safety_banner()
    svc = ExperimentComparisonService()
    comp = svc.compare_experiments(args.id1, args.id2)
    
    if not comp:
        print("Comparison failed. Check IDs.")
        return 1
        
    print(f"Compatibility: {comp.compatibility.value}")
    for n in comp.compatibility_notes:
        print(f"  - {n}")
        
    print(f"\nFinal Assessment: {comp.final_research_assessment.value}")
    print(f"Recommendation: {comp.recommendation}")
    
    return 0
