import argparse
import json
from datetime import datetime
from app.research.replication.service import ReplicationService
from app.research.replication.repository import ReplicationRepository
from app.research.hypothesis_validation.repository import ValidationRepository

def setup_replication_parser(subparsers):
    p = subparsers.add_parser("replication", help="Assess replication & evidence strength of a validation result")
    p.add_argument("validation_id", help="Validation ID")
    p.add_argument("--as-of", help="Historical as-of timestamp (ISO)")
    p.set_defaults(func=run_replication)
    
    p2 = subparsers.add_parser("evidence-strength", help="View a specific evidence strength assessment")
    p2.add_argument("assessment_id", help="Assessment ID")
    p2.set_defaults(func=run_view_replication)

def run_replication(args) -> int:
    val_repo = ValidationRepository()
    val = val_repo.get_validation(args.validation_id)
    if not val:
        print("Validation result not found.")
        return 1
        
    service = ReplicationService()
    as_of_dt = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None
    
    try:
        res = service.evaluate(val, as_of=as_of_dt)
        print(f"Assessment ID: {res.assessment_id}")
        print(f"Generalization: {res.generalization_state.value}")
        print(f"Evidence Strength: {res.evidence_strength.value}")
        print(f"Explanation: {res.explanation}")
        print("---")
        print(f"Independent units: {res.replication.total_independent_units}")
        print(f"Same-dataset replays: {res.replication.same_dataset_units}")
        print(f"Overlapping data units: {res.replication.overlapping_units}")
        if res.replication.multiple_testing_risk:
            print("WARNING: Multiple Testing Risk Detected!")
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1

def run_view_replication(args) -> int:
    repo = ReplicationRepository()
    res = repo.get_result(args.assessment_id)
    if not res:
        print("Replication assessment not found.")
        return 1
    
    print(json.dumps(res.model_dump(), indent=2, default=str))
    return 0
