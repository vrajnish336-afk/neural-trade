import argparse

def setup_portfolio_discovery_parser(subparsers):
    p = subparsers.add_parser("portfolio-discovery", help="Run adaptive portfolio stress discovery")
    p.add_argument("portfolio_id", help="Target Portfolio ID")
    p.set_defaults(func=run_portfolio_discovery)
    
def run_portfolio_discovery(args) -> int:
    print(f"Executing adaptive stress discovery against portfolio {args.portfolio_id}")
    print("WARNING: All questions generated are for research priority only. No live allocations.")
    return 0
