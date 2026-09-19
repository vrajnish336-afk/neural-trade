import argparse
import json
from datetime import datetime
from app.research.hypothesis_validation.validator import HypothesisValidator
from app.research.hypothesis_validation.repository import ValidationRepository
from app.research.synthesis.repository import SynthesisRepository

def setup_validation_parser(subparsers):
    p = subparsers.add_parser("hypothesis-validate", help="Validate a hypothesis")
    p.add_argument("hypothesis_id", help="Hypothesis ID to validate")
    p.add_argument("--as-of", help="Historical as-of timestamp (ISO)")
    p.set_defaults(func=run_validate)
    
    p2 = subparsers.add_parser("hypothesis-validation", help="View a specific validation result")
    p2.add_argument("validation_id", help="Validation Result ID")
    p2.set_defaults(func=run_view_validation)
    
def run_validate(args) -> int:
    syn_repo = SynthesisRepository()
    hyp = syn_repo.get_hypothesis(args.hypothesis_id)
    if not hyp:
        print("Hypothesis not found.")
        return 1
        
    validator = HypothesisValidator()
    as_of_dt = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None
    
    res = validator.validate(hyp, as_of=as_of_dt)
    
    print(f"Validation Result ID: {res.validation_id}")
    print(f"State: {res.validation_state.value}")
    print(f"Falsification: {res.falsification_triggered.value}")
    print(f"Explanation: {res.explanation}")
    return 0
    
def run_view_validation(args) -> int:
    repo = ValidationRepository()
    val = repo.get_validation(args.validation_id)
    if not val:
        print("Validation result not found.")
        return 1
    
    print(json.dumps(val.model_dump(), indent=2, default=str))
    return 0
