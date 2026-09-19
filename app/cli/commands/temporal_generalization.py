import argparse
from datetime import datetime, timezone
from app.research.temporal_generalization.service import TemporalGeneralizationService
from app.research.temporal_generalization.models import WalkForwardType

def setup_temporal_parser(subparsers):
    p = subparsers.add_parser("walk-forward", help="Create a walk-forward run for a candidate")
    p.add_argument("candidate_id", help="Candidate ID")
    p.add_argument("--type", choices=["ROLLING", "EXPANDING"], default="ROLLING")
    p.set_defaults(func=run_walk_forward)
    
    pa = subparsers.add_parser("temporal-generalization", help="Assess a temporal generalization run")
    pa.add_argument("run_id", help="Run ID")
    pa.add_argument("candidate_id", help="Candidate ID")
    pa.set_defaults(func=run_assessment)
    
def run_walk_forward(args) -> int:
    service = TemporalGeneralizationService()
    
    # Mock bounds for CLI trigger
    run_id = service.create_run(
        candidate_id=args.candidate_id,
        dataset_identity="cli_request",
        full_start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        full_end=datetime(2024, 1, 1, tzinfo=timezone.utc),
        train_days=365, val_days=90, forward_days=180, step_days=180,
        wf_type=WalkForwardType(args.type),
        strategy_identity="cli_strat",
        parameter_identity="cli_params",
        as_of=datetime.now(timezone.utc),
        lineage="manual_cli"
    )
    print(f"Created Walk Forward Run: {run_id}")
    return 0

def run_assessment(args) -> int:
    service = TemporalGeneralizationService()
    try:
        as_of = datetime.now(timezone.utc)
        res = service.assess_run(args.run_id, args.candidate_id, WalkForwardType.ROLLING, as_of)
        print(f"Assessment ID: {res.assessment_id}")
        print(f"Overall State: {res.overall_state.value}")
        print(f"Total Windows: {res.total_windows}")
        print(f"Successful Windows: {res.successful_windows}")
        print(f"Dispersion: {res.performance_dispersion:.4f}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
