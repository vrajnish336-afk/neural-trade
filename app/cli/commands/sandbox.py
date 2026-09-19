import argparse
import json
from app.sandbox.service import SandboxService

def setup_sandbox_parser(subparsers):
    p = subparsers.add_parser("code-propose", help="Propose research code via CLI")
    p.add_argument("--code", required=True, help="Path to code file or code string")
    p.add_argument("--identity", required=True, help="Research Identity")
    p.set_defaults(func=run_propose)
    
    p2 = subparsers.add_parser("sandbox", help="View sandbox proposals")
    p2.set_defaults(func=run_view)

def _print_safety_banner():
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("AI-GENERATED CODE IS RESEARCH-ONLY.")
    print("SANDBOX HAS NO BROKER ACCESS.")
    print("==================================================\n")

def run_propose(args) -> int:
    _print_safety_banner()
    svc = SandboxService()
    
    code = args.code
    import os
    if os.path.exists(code):
        with open(code, "r") as f:
            code = f.read()
            
    proposal = svc.propose_code(args.identity, "CLI Proposal", "Generated from CLI", code)
    print(f"Proposed: {proposal.proposal_id} - Status: {proposal.status.value}")
    
    # We do a mock validate to show it works
    from app.core.models import MarketBar
    from datetime import datetime
    bars = [MarketBar(symbol="BTC", timestamp=datetime.utcnow(), open=1, high=1, low=1, close=1, volume=1)]
    valid = svc.validate_proposal(proposal, bars)
    print(f"Validation Result: {valid} - Status: {proposal.status.value}")
    return 0

def run_view(args) -> int:
    _print_safety_banner()
    svc = SandboxService()
    props = svc.repo.get_proposals()
    
    for p in props:
        print(f"[{p.status.value}] {p.proposal_id} | {p.title} | {p.research_identity}")
    return 0
