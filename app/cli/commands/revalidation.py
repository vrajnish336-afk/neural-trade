import argparse
import json
from datetime import datetime
from app.research.revalidation.service import RevalidationService
from app.research.revalidation.repository import RevalidationRepository
from app.research.hypothesis_validation.repository import ValidationRepository
from app.research.replication.repository import ReplicationRepository

def setup_revalidation_parser(subparsers):
    p = subparsers.add_parser("evidence-health", help="Check the drift, decay, and health of a validation result")
    p.add_argument("validation_id", help="Validation ID")
    p.add_argument("--as-of", help="Historical as-of timestamp (ISO)")
    p.set_defaults(func=run_evidence_health)
    
def run_evidence_health(args) -> int:
    val_repo = ValidationRepository()
    val = val_repo.get_validation(args.validation_id)
    if not val:
        print("Validation result not found.")
        return 1
        
    rep_repo = ReplicationRepository()
    vals = rep_repo.get_results_for_hypothesis(val.hypothesis_id)
    rep = vals[0] if vals else None
        
    service = RevalidationService()
    as_of_dt = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None
    
    try:
        res = service.evaluate(val, rep, as_of=as_of_dt)
        print(f"Assessment ID: {res.assessment_id}")
        print(f"Decay State: {res.decay_state.value} (Age: {round(res.evidence_age_days,1) if res.evidence_age_days else 'Unknown'} days)")
        print(f"Drift Flags: {', '.join(res.drift_flags) if res.drift_flags else 'None'}")
        print(f"Original Strength: {res.original_evidence_strength.value}")
        print(f"Current Strength: {res.current_evidence_strength.value}")
        
        if res.revalidation_required:
            print("\n!!! REVALIDATION REQUIRED !!!")
            print("Reasons:")
            for r in res.revalidation_reasons:
                print(f"- {r.value}")
        print(f"\nExplanation: {res.explanation}")
        
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1
