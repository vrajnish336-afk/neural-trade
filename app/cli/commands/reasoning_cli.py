import argparse
from datetime import datetime, timezone
from app.research.reasoning.service import ReasoningService

def setup_reasoning_parser(subparsers):
    p = subparsers.add_parser("reasoning", help="Query and manage the Research Knowledge Reasoning Engine")
    sub = p.add_subparsers(dest="reasoning_command")
    
    status_p = sub.add_parser("status", help="Get summary of the Reasoning Engine")
    status_p.set_defaults(func=run_reasoning_status)
    
    gaps_p = sub.add_parser("gaps", help="View generated research questions for Phase 32")
    gaps_p.set_defaults(func=run_reasoning_gaps)

def run_reasoning_status(args) -> int:
    print("WARNING: RESEARCH REASONING — NOT A TRADING SIGNAL")
    print("WARNING: PAPER / RESEARCH ONLY — LIVE TRADING DISABLED")
    
    svc = ReasoningService()
    as_of = datetime.now(timezone.utc)
    summary = svc.get_summary(as_of)
    
    print("\nReasoning Engine Summary:")
    print(f"Total Inferences: {summary.total_reasoning_results}")
    print(f"Conditional Inferences: {summary.conditional_inferences}")
    print(f"Conflicted Inferences: {summary.conflicted_inferences}")
    print(f"Research Questions Pending Review: {summary.research_gap_count}")
    return 0

def run_reasoning_gaps(args) -> int:
    svc = ReasoningService()
    questions = svc.get_questions_for_review()
    print(f"Found {len(questions)} Pending Research Questions:")
    for q in questions:
        print(f"\n[{q.question_id}] Priority {q.priority_score}")
        print(f"Q: {q.research_question}")
        print(f"Status: {q.status.value}")
    return 0
