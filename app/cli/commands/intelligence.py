import argparse
from datetime import datetime, timezone
from app.intelligence.service import WorldIntelligenceService

def setup_intelligence_parser(subparsers):
    parser = subparsers.add_parser("world", help="Fetch and aggregate world intelligence (PAPER/RESEARCH ONLY)")
    parser.set_defaults(func=run_world)
    
    ctx_parser = subparsers.add_parser("world-context", help="View aggregated world context")
    ctx_parser.set_defaults(func=run_context)

def _print_safety_banner():
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("WORLD INTELLIGENCE IS CONTEXT, NOT A TRADING SIGNAL.")
    print("==================================================\n")

def run_world(args) -> int:
    _print_safety_banner()
    svc = WorldIntelligenceService()
    print("Fetching world intelligence...")
    svc.fetch_and_store_all()
    print("Done.")
    return 0

def run_context(args) -> int:
    _print_safety_banner()
    svc = WorldIntelligenceService()
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    ctx = svc.aggregate_context(as_of=now)
    
    print(f"WORLD CONTEXT AS OF {ctx.as_of.isoformat()}")
    print("-" * 50)
    print(f"Sentiment Summary: {ctx.sentiment_summary if ctx.sentiment_summary is not None else 'UNKNOWN'}")
    print(f"Fear & Greed:      {ctx.fear_and_greed_classification or 'NOT_AVAILABLE'}")
    print(f"Macro Status:      {ctx.macro_summary}")
    print(f"Flow Status:       {ctx.flow_summary}")
    print(f"Sources:           {ctx.source_count} ({ctx.high_quality_source_count} High Quality)")
    print(f"Lineage Hash:      {ctx.lineage_hash}")
    return 0
