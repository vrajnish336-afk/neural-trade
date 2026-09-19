import argparse
from datetime import datetime, timezone
from app.research.knowledge_intelligence.service import KnowledgeIntelligenceService

def setup_knowledge_intelligence_parser(subparsers):
    p = subparsers.add_parser("knowledge-synthesize", help="Synthesize knowledge claims from historical research")
    p.add_argument("research_identity", help="Research Identity Hash")
    p.set_defaults(func=run_knowledge_synthesize)
    
def run_knowledge_synthesize(args) -> int:
    print(f"Synthesizing Knowledge for {args.research_identity}...")
    print("WARNING: RESEARCH KNOWLEDGE — NOT A TRADING SIGNAL.")
    print("WARNING: PAPER / RESEARCH ONLY — LIVE TRADING DISABLED.")
    
    svc = KnowledgeIntelligenceService()
    claim = svc.run_synthesis(args.research_identity, datetime.now(timezone.utc))
    
    if claim:
        print(f"\nClaim ID: {claim.claim_id}")
        print(f"State: {claim.knowledge_state.value}")
        print(f"Statement: {claim.canonical_statement}")
        print(f"Scope Datasets: {claim.scope.dataset_scope}")
        print(f"Independent Evidence Units: {claim.independent_evidence_count}")
        return 0
    else:
        print("\nInsufficient evidence to synthesize knowledge claim.")
        return 1
