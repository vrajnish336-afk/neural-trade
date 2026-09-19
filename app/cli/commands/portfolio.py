import argparse
import sys
from typing import List
from app.research.portfolio_service import ResearchPortfolioService

def setup_portfolio_parser(subparsers):
    portfolio_parser = subparsers.add_parser("research-candidates", help="View the Research Candidate Portfolio (Phase 21)")
    portfolio_parser.add_argument("--limit", type=int, default=50, help="Max candidates to show")
    portfolio_parser.set_defaults(func=run_portfolio)
    
    compare_parser = subparsers.add_parser("research-compare", help="Compare research candidates by identity (Phase 21)")
    compare_parser.add_argument("identities", nargs="+", help="Identity hashes to compare")
    compare_parser.set_defaults(func=run_compare)
    
    history_parser = subparsers.add_parser("research-history", help="Longitudinal candidate tracking (Phase 22)")
    history_parser.add_argument("identity", help="Identity hash to track")
    history_parser.add_argument("--as-of", type=str, help="ISO format timestamp barrier (e.g. 2026-01-01T00:00:00)")
    history_parser.set_defaults(func=run_history)
    
    transitions_parser = subparsers.add_parser("research-transitions", help="Longitudinal state transitions (Phase 22)")
    transitions_parser.add_argument("identity", help="Identity hash to track")
    transitions_parser.set_defaults(func=run_transitions)

    evolution_parser = subparsers.add_parser("research-evolution", help="Longitudinal evolution summary (Phase 22)")
    evolution_parser.set_defaults(func=run_evolution)

def _print_warning():
    print("\n========================================================")
    print("WARNING: PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("This output is for research evidence comparison only.")
    print("========================================================\n")

def run_portfolio(args) -> int:
    _print_warning()
    service = ResearchPortfolioService()
    portfolio = service.get_portfolio(limit=args.limit)
    if not portfolio:
        print("No research candidates found.")
        return 0
        
    print(f"Loaded {len(portfolio)} candidates.\n")
    print(f"{'IDENTITY':<15} | {'STRATEGY':<15} | {'PRIORITY':<10} | {'SCORE':<5} | {'FWD OBS':<7} | {'HEALTH':<20}")
    print("-" * 85)
    for c in portfolio:
        print(f"{c.identity_hash[:13]:<15} | {c.strategy[:15]:<15} | {c.priority.value:<10} | {c.evidence_score.total_score:<5} | {c.forward_observation_count:<7} | {c.current_health.value:<20}")
    return 0

def run_compare(args) -> int:
    _print_warning()
    service = ResearchPortfolioService()
    if len(args.identities) < 2:
        print("Error: Must provide at least two identity hashes to compare.")
        return 1
        
    matrix = service.compare_candidates(args.identities)
    print(f"Comparability: {matrix.comparability.value}")
    print(f"Conclusion: {matrix.conclusion}\n")
    
    if matrix.differences:
        print("Differences:")
        for d in matrix.differences:
            print(f"  - {d}")
        print()
        
    print("Candidate Ranking (by Evidence Score, NOT purely PnL):")
    for idx, c in enumerate(matrix.candidates):
        print(f"{idx+1}. {c.identity_hash} ({c.strategy})")
        print(f"   Priority: {c.priority.value} | Score: {c.evidence_score.total_score}")
        print(f"   Health: {c.current_health.value} | Fwd Obs: {c.forward_observation_count}")
        print(f"   Conflicts: {c.unresolved_conflicts} | Missing Lineage: {c.missing_lineage}")
        print(f"   Priority Reasons: {', '.join(c.priority_reasons)}\n")
    return 0

def run_history(args) -> int:
    _print_warning()
    from app.research.longitudinal_service import LongitudinalCandidateTracker
    from datetime import datetime
    
    as_of = None
    if args.as_of:
        try:
            as_of = datetime.fromisoformat(args.as_of)
        except ValueError:
            print("Error: Invalid --as-of timestamp format. Use ISO format (e.g., 2026-01-01T12:00:00)")
            return 1
            
    tracker = LongitudinalCandidateTracker()
    timeline = tracker.get_history(args.identity, as_of=as_of)
    
    print(f"LONGITUDINAL RESEARCH TIMELINE: {args.identity}")
    if as_of:
        print(f"AS-OF BARRIER: {as_of.isoformat()} (Future evidence is hidden)")
    print("=" * 60)
    
    if not timeline.events:
        print("No historical events found for this candidate.")
        return 0
        
    for evt in timeline.events:
        print(f"\n[{evt.timestamp.isoformat()}] {evt.event_type.value}")
        for t in evt.transitions:
            print(f"  -> {t.field_name.upper()}: {t.previous_state} -> {t.new_state}")
            print(f"     Reason: {t.reason}")
            
    snap = timeline.latest_snapshot
    if snap:
        print("\n" + "=" * 60)
        print("FINAL STATE REACHED (AS OF SPECIFIED TIME):")
        print(f"Priority: {snap.priority.value} | Health: {snap.current_health.value} | Score: {snap.evidence_score.total_score}")
        print(f"Fwd Observations: {snap.forward_observation_count} | Unresolved Conflicts: {snap.unresolved_conflicts}")
        
    return 0

def run_transitions(args) -> int:
    _print_warning()
    from app.research.longitudinal_service import LongitudinalCandidateTracker
    tracker = LongitudinalCandidateTracker()
    timeline = tracker.get_history(args.identity)
    
    print(f"RESEARCH TRANSITIONS: {args.identity}")
    print("=" * 60)
    
    has_transitions = False
    for evt in timeline.events:
        if evt.transitions:
            has_transitions = True
            print(f"[{evt.timestamp.isoformat()}]")
            for t in evt.transitions:
                print(f"  {t.field_name.upper()}: {t.previous_state} -> {t.new_state}")
                print(f"  Explanation: {t.reason}")
    if not has_transitions:
        print("No meaningful state transitions found.")
    return 0

def run_evolution(args) -> int:
    _print_warning()
    from app.research.portfolio_service import ResearchPortfolioService
    service = ResearchPortfolioService()
    portfolio = service.get_portfolio(limit=50)
    print("RESEARCH EVOLUTION SUMMARY (All Candidates)")
    print("=" * 60)
    for c in portfolio:
        print(f"Candidate: {c.identity_hash}")
        print(f"  Current Priority: {c.priority.value}")
        print(f"  Current Health: {c.current_health.value}")
        print(f"  Forward Observations: {c.forward_observation_count}")
        print(f"  Conflicts: {c.unresolved_conflicts}")
        print("-" * 30)
    return 0

