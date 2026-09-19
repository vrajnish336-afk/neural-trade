import argparse
import json
from datetime import datetime
from app.research.causal_experiments.service import CausalExperimentService
from app.research.causal_experiments.repository import CausalExperimentRepository
from app.research.causality.repository import CausalRepository

def setup_causal_experiment_parser(subparsers):
    p = subparsers.add_parser("causal-experiment-design", help="Design causal experiments for a hypothesis")
    p.add_argument("hypothesis_id", help="Hypothesis ID")
    p.set_defaults(func=run_design)
    
    pa = subparsers.add_parser("causal-experiment-approve", help="Approve an experiment for research")
    pa.add_argument("hypothesis_id", help="Hypothesis ID")
    pa.add_argument("experiment_id", help="Experiment ID")
    pa.set_defaults(func=run_approve)
    
    pr = subparsers.add_parser("causal-experiment-run", help="Run a controlled causal experiment")
    pr.add_argument("hypothesis_id", help="Hypothesis ID")
    pr.add_argument("experiment_id", help="Experiment ID")
    pr.set_defaults(func=run_execute)
    
def run_design(args) -> int:
    cau_repo = CausalRepository()
    assessments = cau_repo.get_results_for_hypothesis(args.hypothesis_id)
    if not assessments:
        print("Causal assessment not found.")
        return 1
        
    service = CausalExperimentService()
    designs = service.generate_designs(assessments[0])
    
    for d in designs:
        print(f"\nExperiment ID: {d.experiment_id}")
        print(f"Status: {d.status.value}")
        print(f"Question: {d.research_question}")
        print(f"Focal Var: {d.focal_variable}")
        print(f"Controls: {json.dumps(d.control_variables)}")
    return 0

def run_approve(args) -> int:
    service = CausalExperimentService()
    try:
        success = service.approve_experiment(args.experiment_id, args.hypothesis_id)
        if success:
            print("Experiment APPROVED_FOR_RESEARCH.")
            return 0
        else:
            print("Approval failed.")
            return 1
    except ValueError as e:
        print(f"Error: {e}")
        return 1

def run_execute(args) -> int:
    service = CausalExperimentService()
    try:
        res = service.run_experiment(args.experiment_id, args.hypothesis_id)
        print(f"\nResult ID: {res.result_id}")
        print(f"Result Status: {res.result_status.value}")
        print(f"Confounding Status: {res.confounding_status}")
        print(f"Control: {res.control_condition}")
        print(f"Treatment: {res.treatment_condition}")
        print(f"Outcome: {res.observed_outcome}")
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1
