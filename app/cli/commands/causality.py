import argparse
import json
from datetime import datetime
from app.research.causality.service import CausalService
from app.research.causality.repository import CausalRepository
from app.research.hypothesis_validation.repository import ValidationRepository
from app.research.replication.repository import ReplicationRepository
from app.research.revalidation.repository import RevalidationRepository
from app.research.consensus.repository import ConsensusRepository

def setup_causality_parser(subparsers):
    p = subparsers.add_parser("causality", help="Check the causal evidence level of a research hypothesis")
    p.add_argument("hypothesis_id", help="Hypothesis ID")
    p.add_argument("--as-of", help="Historical as-of timestamp (ISO)")
    p.set_defaults(func=run_causality)
    
def run_causality(args) -> int:
    val_repo = ValidationRepository()
    vals = val_repo.get_results_for_hypothesis(args.hypothesis_id)
    if not vals:
        print("Validation result not found.")
        return 1
    val = vals[0]
        
    con_repo = ConsensusRepository()
    cons = con_repo.get_results_for_hypothesis(args.hypothesis_id)
    if not cons:
        print("Consensus assessment not found.")
        return 1
    con = cons[0]
    
    rep_repo = ReplicationRepository()
    reps = rep_repo.get_results_for_hypothesis(args.hypothesis_id)
    rep = reps[0] if reps else None
    
    rev_repo = RevalidationRepository()
    revs = rev_repo.get_results_for_hypothesis(args.hypothesis_id)
    rev = revs[0] if revs else None
        
    service = CausalService()
    as_of_dt = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None
    
    try:
        res = service.evaluate(args.hypothesis_id, val.research_identity, val, con, rep, rev, as_of=as_of_dt)
        print(f"Assessment ID: {res.assessment_id}")
        print(f"Causal Level: {res.causal_level.value}")
        print(f"Causal State: {res.assessment_state.value}")
        print(f"Temporal Verified: {res.temporal_ordering_verified}")
        
        if res.mechanisms:
            print("\nCandidate Mechanisms:")
            for m in res.mechanisms:
                print(f"- {m.description} (Supp: {m.supporting_evidence_count}, Con: {m.contradicting_evidence_count})")
                
        if res.confounders:
            print("\nConfounding Risks:")
            for c in res.confounders:
                print(f"- {c.description} (Variables: {', '.join(c.overlapping_variables)})")
                
        if res.alternatives:
            print("\nAlternative Explanations:")
            for a in res.alternatives:
                print(f"- {a.description}")
                
        print("\nLIMITATION:")
        print(res.limitations)
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1
