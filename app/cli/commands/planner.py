import argparse
import json
from datetime import datetime
from app.research.planner.planner import ResearchDecisionPlanner

def setup_planner_parser(subparsers):
    p = subparsers.add_parser("research-plan", help="Generate research priorities")
    p.add_argument("--as-of", help="Historical as-of timestamp (ISO)")
    p.set_defaults(func=run_plan)
    
    p2 = subparsers.add_parser("research-plan-approve", help="Approve a research decision")
    p2.add_argument("id", help="Decision ID")
    p2.set_defaults(func=run_approve)

    p3 = subparsers.add_parser("research-priorities", help="List ranked research priorities from memory")
    p3.set_defaults(func=run_priorities)

    p4 = subparsers.add_parser("research-decision", help="View a specific decision")
    p4.add_argument("id", help="Decision ID")
    p4.set_defaults(func=run_view_decision)

def run_plan(args) -> int:
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("RESEARCH PRIORITY IS NOT PROFITABILITY.")
    print("==================================================\n")
    
    planner = ResearchDecisionPlanner()
    as_of_dt = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None
    
    decisions = planner.generate_plan(as_of=as_of_dt)
    
    if not decisions:
        print("No research priorities discovered.")
        return 0
        
    for d in decisions[:10]:
        print(f"[{d.priority:.2f}] {d.recommended_action.value} -> ID: {d.decision_id}")
        print(f"    Rationale: {d.rationale}")
        
    return 0

def run_approve(args) -> int:
    planner = ResearchDecisionPlanner()
    if planner.approve_decision(args.id):
        print("Decision approved for research queueing.")
        return 0
    else:
        print("Failed to approve. Decision may not exist or is not in REVIEW_REQUIRED state.")
        return 1

def run_priorities(args) -> int:
    planner = ResearchDecisionPlanner()
    decisions = planner.repo.get_ranked_decisions()
    if not decisions:
        print("No ranked decisions found.")
        return 0
    for d in decisions[:10]:
        print(f"[{d.priority:.2f}] {d.status.value}: {d.decision_id}")
    return 0

def run_view_decision(args) -> int:
    planner = ResearchDecisionPlanner()
    dec = planner.repo.get_decision(args.id)
    if dec:
        print(json.dumps(dec.model_dump(), indent=2, default=str))
        return 0
    print("Decision not found.")
    return 1
