import argparse
import json
from datetime import datetime
from app.research.consensus.service import ConsensusService
from app.research.consensus.repository import ConsensusRepository
from app.research.hypothesis_validation.repository import ValidationRepository
from app.research.replication.repository import ReplicationRepository
from app.research.revalidation.repository import RevalidationRepository

def setup_consensus_parser(subparsers):
    p = subparsers.add_parser("consensus", help="Check the consensus of a research hypothesis")
    p.add_argument("hypothesis_id", help="Hypothesis ID")
    p.add_argument("--as-of", help="Historical as-of timestamp (ISO)")
    p.set_defaults(func=run_consensus)
    
def run_consensus(args) -> int:
    val_repo = ValidationRepository()
    vals = val_repo.get_results_for_hypothesis(args.hypothesis_id)
    if not vals:
        print("Validation result not found.")
        return 1
    val = vals[0]
        
    rep_repo = ReplicationRepository()
    reps = rep_repo.get_results_for_hypothesis(args.hypothesis_id)
    rep = reps[0] if reps else None
    
    rev_repo = RevalidationRepository()
    revs = rev_repo.get_results_for_hypothesis(args.hypothesis_id)
    rev = revs[0] if revs else None
        
    service = ConsensusService()
    as_of_dt = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None
    
    try:
        res = service.evaluate(args.hypothesis_id, val.research_identity, val, rep, rev, as_of=as_of_dt)
        print(f"Assessment ID: {res.assessment_id}")
        print(f"Consensus State: {res.state.value}")
        print(f"Independent Support: {res.independent_support_count}")
        print(f"Independent Contradict: {res.independent_contradict_count}")
        
        if res.conditional_conditions:
            print(f"Conditional Bounds: {', '.join(res.conditional_conditions)}")
            
        if res.conflicts:
            print("\nConflicts Detected:")
            for c in res.conflicts:
                print(f"- [{c.severity.value}] {c.conflict_type.value}: {c.description} (Resolution: {c.resolution.value})")
                
        if res.research_gaps:
            print("\nResearch Gaps Emitted to Planner:")
            for g in res.research_gaps:
                print(f"- {g}")
                
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1
