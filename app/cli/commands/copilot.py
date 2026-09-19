import argparse
from datetime import datetime, timezone
from app.copilot.models import CopilotRequest
from app.copilot.agent import CopilotAgent

def setup_copilot_parser(subparsers):
    parser = subparsers.add_parser("copilot", help="Ask the Research Intelligence Assistant (PAPER/RESEARCH ONLY)")
    parser.add_argument("--question", required=True, help="Question to ask")
    parser.add_argument("--context", default="lessons,world_intelligence,evolution_proposals,forecasts", help="Comma-separated domains")
    parser.add_argument("--symbol", default=None, help="Symbol filter")
    parser.add_argument("--as-of", default=None, help="ISO timestamp for historical research")
    parser.set_defaults(func=run_copilot)

def _print_safety_banner():
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("AI COPILOT IS READ-ONLY RESEARCH ASSISTANCE.")
    print("AI COPILOT CANNOT EXECUTE TRADES.")
    print("==================================================\n")

def run_copilot(args) -> int:
    _print_safety_banner()
    
    as_of_dt = datetime.fromisoformat(args.as_of) if args.as_of else datetime.utcnow().replace(tzinfo=timezone.utc)
    scope = [s.strip() for s in args.context.split(",")]
    
    req = CopilotRequest(
        question=args.question,
        as_of=as_of_dt,
        context_scope=scope,
        symbol=args.symbol
    )
    
    agent = CopilotAgent()
    resp = agent.ask(req)
    
    print(f"AS OF: {resp.as_of.isoformat()}")
    print(f"SOURCES: {', '.join(resp.evidence_references)}")
    if resp.is_fallback:
        print("STATUS: DETERMINISTIC FALLBACK")
    print("-" * 50)
    print("ANSWER:")
    print(resp.answer)
    print("-" * 50)
    if resp.limitations:
        print(f"LIMITATIONS: {', '.join(resp.limitations)}")
        
    return 0
