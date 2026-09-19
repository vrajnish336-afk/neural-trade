import argparse
from app.research.continuous_orchestrator import ContinuousResearchOrchestrator
from app.research.continuous_models import ResearchCycleState

def setup_continuous_parser(subparsers):
    p = subparsers.add_parser("continuous-cycle", help="Start or tick the continuous research cycle")
    p.set_defaults(func=run_cycle)
    
    p2 = subparsers.add_parser("continuous-cycle-status", help="Show active research cycle status")
    p2.set_defaults(func=run_status)
    
    p3 = subparsers.add_parser("continuous-cycle-pause", help="Pause a research cycle")
    p3.add_argument("id", help="Cycle ID")
    p3.set_defaults(func=run_pause)
    
    p4 = subparsers.add_parser("continuous-cycle-resume", help="Resume a research cycle")
    p4.add_argument("id", help="Cycle ID")
    p4.set_defaults(func=run_resume)
    
    p5 = subparsers.add_parser("continuous-cycle-cancel", help="Cancel a research cycle")
    p5.add_argument("id", help="Cycle ID")
    p5.set_defaults(func=run_cancel)

def _print_safety_banner():
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("CONTINUOUS RESEARCH ORCHESTRATION ONLY.")
    print("==================================================\n")

def run_cycle(args) -> int:
    _print_safety_banner()
    orch = ContinuousResearchOrchestrator()
    
    active = orch.repo.get_active_cycle()
    if not active:
        print("Starting new research cycle...")
        active = orch.start_new_cycle()
        
    print(f"Active Cycle ID: {active.cycle_id}")
    print(f"State Before: {active.state.value}")
    
    orch.tick()
    
    active = orch.repo.get_cycle(active.cycle_id)
    print(f"State After: {active.state.value}")
    if active.state == ResearchCycleState.WAITING_FOR_RESEARCH_APPROVAL:
        print("Cycle paused. Waiting for human research approval.")
        print("Use 'ntrade evolution-approve <id>' to approve proposals.")
    return 0

def run_status(args) -> int:
    _print_safety_banner()
    orch = ContinuousResearchOrchestrator()
    active = orch.repo.get_active_cycle()
    if active:
        print(f"Active Cycle: {active.cycle_id}")
        print(f"State: {active.state.value}")
        print(f"Proposals Generated: {len(active.generated_proposal_ids)}")
        print(f"Proposals Completed: {len(active.completed_proposal_ids)}")
    else:
        print("No active research cycle.")
    return 0

def run_pause(args) -> int:
    orch = ContinuousResearchOrchestrator()
    if orch.pause_cycle(args.id):
        print("Cycle paused.")
    else:
        print("Failed to pause cycle.")
    return 0

def run_resume(args) -> int:
    orch = ContinuousResearchOrchestrator()
    if orch.resume_cycle(args.id):
        print("Cycle resumed.")
    else:
        print("Failed to resume cycle.")
    return 0

def run_cancel(args) -> int:
    orch = ContinuousResearchOrchestrator()
    if orch.cancel_cycle(args.id):
        print("Cycle cancelled.")
    else:
        print("Failed to cancel cycle.")
    return 0
