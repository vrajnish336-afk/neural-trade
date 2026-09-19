import argparse
from app.learning.evolution_engine import ControlledEvolutionEngine
import json

def setup_evolution_parser(subparsers):
    p = subparsers.add_parser("evolution-status", help="Show evolution proposals")
    p.set_defaults(func=run_status)
    
    p2 = subparsers.add_parser("evolution-approve", help="Approve an evolution proposal")
    p2.add_argument("id", help="Proposal ID")
    p2.set_defaults(func=run_approve)
    
    p3 = subparsers.add_parser("evolution-run", help="Run an approved proposal")
    p3.add_argument("id", help="Proposal ID")
    p3.set_defaults(func=run_execute)
    
def _print_safety_banner():
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("CONTROLLED SELF-EVOLUTION ONLY.")
    print("==================================================\n")

def run_status(args) -> int:
    _print_safety_banner()
    engine = ControlledEvolutionEngine()
    props = engine.repo.get_proposals()
    print(f"Total Evolution Proposals: {len(props)}")
    for p in props:
        print(f"ID: {p.proposal_id}")
        print(f"Question: {p.research_question}")
        print(f"State: {p.state.value}")
        print(f"Answer: {p.final_research_answer.value}\n")
    return 0

def run_approve(args) -> int:
    _print_safety_banner()
    engine = ControlledEvolutionEngine()
    if engine.approve_proposal(args.id):
        print("Approved for research sandbox execution.")
    else:
        print("Failed to approve.")
    return 0

def run_execute(args) -> int:
    _print_safety_banner()
    engine = ControlledEvolutionEngine()
    if engine.execute_proposal(args.id):
        print("Sandbox experiment created successfully.")
        engine.validate_experiment(args.id)
        p = engine.repo.get_proposal(args.id)
        print(f"Research Answer: {p.final_research_answer.value}")
    else:
        print("Failed to execute.")
    return 0
