import argparse
import sys
import json

def setup_learning_parser(subparsers):
    learning_parser = subparsers.add_parser("lessons", help="View the Ranked Lessons Bank (Phase 23)")
    learning_parser.add_argument("--identity", type=str, help="Filter by identity hash")
    learning_parser.set_defaults(func=run_lessons)
    
    extract_parser = subparsers.add_parser("extract-lessons", help="Extract lessons deterministically")
    extract_parser.add_argument("identity", help="Identity hash")
    extract_parser.set_defaults(func=run_extract)

    proposals_parser = subparsers.add_parser("evolution-proposals", help="View evolution parameter proposals")
    proposals_parser.set_defaults(func=run_proposals)
    
    propose_parser = subparsers.add_parser("propose-evolution", help="Propose parameter change safely")
    propose_parser.add_argument("identity", help="Identity hash")
    propose_parser.add_argument("strategy", help="Strategy name")
    propose_parser.add_argument("params_json", help="Proposed parameters as JSON string")
    propose_parser.add_argument("reason", help="Reasoning")
    propose_parser.set_defaults(func=run_propose)

def _print_warning():
    print("\n========================================================")
    print("WARNING: PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("Lessons and proposals do not predict future profitability.")
    print("========================================================\n")

def run_lessons(args) -> int:
    _print_warning()
    from app.learning.repository import LearningRepository
    from app.learning.lesson_engine import LessonEngine
    
    repo = LearningRepository()
    engine = LessonEngine()
    
    lessons = repo.get_lessons(args.identity)
    if not lessons:
        print("No lessons found.")
        return 0
        
    ranked = engine.rank_lessons(lessons)
    print(f"Loaded {len(ranked)} ranked lessons.\n")
    print(f"{'LESSON_ID':<36} | {'STRATEGY':<15} | {'REGIME':<15} | {'RANK SCORE':<10} | {'STATE':<15}")
    print("-" * 105)
    for l in ranked:
        print(f"{l.lesson_id:<36} | {l.strategy[:15]:<15} | {str(l.regime)[:15]:<15} | {l.evidence_count*l.confidence_score:<10.2f} | {l.state.value:<15}")
    return 0

def run_extract(args) -> int:
    _print_warning()
    from app.learning.lesson_engine import LessonEngine
    
    engine = LessonEngine()
    new_lessons = engine.extract_lessons(args.identity)
    
    print(f"Extracted {len(new_lessons)} new deterministic lessons.")
    for l in new_lessons:
        print(f" - [{l.state.value}] {l.lesson_statement}")
    return 0

def run_proposals(args) -> int:
    _print_warning()
    from app.learning.repository import LearningRepository
    
    repo = LearningRepository()
    proposals = repo.get_proposals()
    
    if not proposals:
        print("No parameter proposals found.")
        return 0
        
    for p in proposals:
        print(f"PROPOSAL: {p.proposal_id} ({p.state.value})")
        print(f"Identity: {p.identity_hash}")
        print(f"Strategy: {p.strategy}")
        print(f"Reason:   {p.reason}")
        print(f"Baseline: {p.baseline_parameters_json}")
        print(f"Proposed: {p.proposed_parameters_json}")
        print("-" * 60)
    return 0

def run_propose(args) -> int:
    _print_warning()
    from app.learning.evolution_service import EvolutionService
    from app.learning.repository import LearningRepository
    
    repo = LearningRepository()
    svc = EvolutionService()
    
    # We fake supporting lessons for CLI testing convenience
    lessons = repo.get_lessons(args.identity)
    try:
        proposed_params = json.loads(args.params_json)
    except json.JSONDecodeError:
        print("Error: params_json must be valid JSON.")
        return 1
        
    proposal = svc.propose_change(
        identity_hash=args.identity,
        strategy=args.strategy,
        proposed_params=proposed_params,
        supporting_lessons=lessons[:2],
        reason=args.reason
    )
    
    if proposal:
        print(f"SUCCESS. Safely proposed parameter evolution: {proposal.proposal_id}")
    else:
        print("REJECTED. Proposal failed deterministic safety validation.")
    return 0
