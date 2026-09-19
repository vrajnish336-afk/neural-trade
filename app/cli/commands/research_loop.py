import argparse
import logging
from app.database.schema import init_db
from app.research.loop_orchestrator import ResearchLoopOrchestrator

logger = logging.getLogger(__name__)

def setup_research_loop_parser(subparsers):
    parser = subparsers.add_parser("research-loop", help="Execute AI Research Loop (Map hypotheses and run historical research)")
    parser.set_defaults(func=run_research_loop)

def run_research_loop(args):
    init_db()
    print("Starting AI Research Loop...")
    
    orchestrator = ResearchLoopOrchestrator()
    
    mapped = orchestrator.process_new_hypotheses()
    print(f"Evaluated {mapped} AI hypotheses into Research Opportunities.")
    
    queued = orchestrator.queue_opportunities_for_research()
    print(f"Queued {queued} opportunities into active research requests.")
    
    executed = orchestrator.execute_pending_requests()
    print(f"Executed {executed} pending historical research requests.")
    
    print("AI Research Loop Complete.")
    return 0
