import argparse

def setup_discrepancy_isolation_parser(subparsers):
    p = subparsers.add_parser("isolation-plan", help="Create OFAT isolation plan")
    p.add_argument("discrepancy_id", help="Target Discrepancy ID")
    p.set_defaults(func=run_plan)
    
def run_plan(args) -> int:
    print(f"Creating Controlled Isolation Plan for Discrepancy {args.discrepancy_id}")
    print("WARNING: CONTROLLED RESEARCH ISOLATION — NOT A TRADING SIGNAL.")
    print("WARNING: MUST REQUIRE HUMAN APPROVAL.")
    return 0
