import argparse
import logging
import json
from datetime import datetime, timezone
from app.database.schema import init_db
from app.research.forward_validation_service import ForwardValidationService
from app.research.forward_validation_models import FrozenSpecification

logger = logging.getLogger(__name__)

def setup_forward_validation_parser(subparsers):
    fv_parser = subparsers.add_parser("forward-validate", help="Trigger a forward paper validation run")
    fv_parser.add_argument("identity_hash", type=str, help="Research Identity Hash")
    fv_parser.add_argument("reference_experiment_id", type=str, help="Historical Experiment ID to freeze")
    fv_parser.set_defaults(func=run_forward_validate)
    
    status_parser = subparsers.add_parser("forward-validation", help="Check status of a forward validation run")
    status_parser.add_argument("validation_id", type=str, help="Validation Run ID")
    status_parser.set_defaults(func=run_check_validation)
    
def run_forward_validate(args):
    init_db()
    service = ForwardValidationService()
    
    # 1. We need to construct the frozen spec from the reference experiment
    try:
        with service._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT experiment_json FROM research_experiments WHERE id = ?", (args.reference_experiment_id,))
            row = cursor.fetchone()
            if not row:
                print(f"Error: Could not find reference experiment {args.reference_experiment_id}")
                return 1
                
            exp_data = json.loads(row[0])
            # Parse out the required fields for freezing
            hist_end_str = exp_data.get("dataset_identity", {}).get("end")
            if not hist_end_str:
                print("Error: Reference experiment dataset lacks an 'end' boundary.")
                return 1
                
            hist_end = datetime.fromisoformat(hist_end_str)
            
            spec = FrozenSpecification(
                strategy=exp_data.get("strategy", "Unknown"),
                symbols=exp_data.get("symbols", []),
                timeframe=exp_data.get("timeframe", "1d"),
                historical_end=hist_end,
                configuration=exp_data.get("configuration", "default"),
                random_seed=exp_data.get("random_seed", 42),
                starting_capital=exp_data.get("starting_capital", 10000.0)
                # cost_config uses default internally
            )
            
    except Exception as e:
        print(f"Failed to parse reference experiment: {e}")
        return 1
        
    print(f"Freezing specification for {spec.strategy} on {spec.symbols}...")
    run = service.create_validation_request(args.identity_hash, args.reference_experiment_id, spec)
    
    if not run:
        print("Failed to create validation request (may already be running or exist).")
        return 1
        
    print(f"Created Forward Validation Run: {run.validation_id}")
    print("Executing...")
    
    service.execute_validation(run)
    
    print(f"Execution complete. Final State: {run.state.value}")
    if run.drift_state:
        print(f"Performance Drift: {run.drift_state.value}")
    if run.failure_reason:
        print(f"Reason: {run.failure_reason}")
        
    return 0
    
def run_check_validation(args):
    init_db()
    service = ForwardValidationService()
    run = service.get_run(args.validation_id)
    if not run:
        print("Not found.")
        return 1
        
    print("\n" + "="*50)
    print("FORWARD PAPER VALIDATION")
    print("="*50)
    print(f"Validation ID : {run.validation_id}")
    print(f"Identity Hash : {run.identity_hash}")
    print(f"State         : {run.state.value}")
    if run.drift_state:
        print(f"Drift State   : {run.drift_state.value}")
    print("-" * 50)
    print("FROZEN SPECIFICATION:")
    print(f"Strategy      : {run.frozen_specification.strategy}")
    print(f"Symbols       : {run.frozen_specification.symbols}")
    print(f"Hist Boundary : {run.frozen_specification.historical_end}")
    if run.dataset_identity:
        print("-" * 50)
        print("FORWARD DATASET:")
        print(f"Start         : {run.dataset_identity.get('start')}")
        print(f"End           : {run.dataset_identity.get('end')}")
        print(f"Row Count     : {run.dataset_identity.get('row_count')}")
    if run.failure_reason:
        print("-" * 50)
        print(f"ERROR: {run.failure_reason}")
    print("="*50)
    return 0
