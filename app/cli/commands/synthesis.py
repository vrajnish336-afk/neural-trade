import argparse
import json
from datetime import datetime
from app.research.synthesis.synthesizer import ResearchKnowledgeSynthesizer
from app.research.synthesis.hypothesis import HypothesisGenerator
from app.research.synthesis.repository import SynthesisRepository
from app.research.synthesis.models import HypothesisStatus

def setup_synthesis_parser(subparsers):
    p = subparsers.add_parser("research-synthesis", help="Synthesize knowledge for a given research identity")
    p.add_argument("identity", help="Research Identity Hash")
    p.add_argument("--as-of", help="Historical as-of timestamp (ISO)")
    p.set_defaults(func=run_synthesis)
    
    p2 = subparsers.add_parser("hypotheses", help="List all generated hypotheses")
    p2.set_defaults(func=run_list_hypotheses)

    p3 = subparsers.add_parser("hypothesis-generate", help="Generate hypotheses from a synthesis")
    p3.add_argument("synthesis_id", help="Synthesis ID")
    p3.set_defaults(func=run_hypothesis_generate)
    
    p4 = subparsers.add_parser("hypothesis-approve", help="Approve a hypothesis for research")
    p4.add_argument("id", help="Hypothesis ID")
    p4.set_defaults(func=run_hypothesis_approve)

def run_synthesis(args) -> int:
    synth = ResearchKnowledgeSynthesizer()
    as_of_dt = datetime.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None
    
    res = synth.synthesize(args.identity, as_of=as_of_dt)
    if res:
        print(f"Synthesis ID: {res.synthesis_id}")
        print(f"State: {res.confidence_state.value}")
        print(f"Supporting: {len(res.supporting_evidence)} | Contradicting: {len(res.contradictory_evidence)}")
        return 0
    print("Could not generate synthesis.")
    return 1

def run_list_hypotheses(args) -> int:
    repo = SynthesisRepository()
    hyps = repo.get_all_hypotheses()
    for h in hyps[:10]:
        print(f"[{h.status.value}] {h.hypothesis_id}: {h.hypothesis_text[:50]}...")
    return 0

def run_hypothesis_generate(args) -> int:
    repo = SynthesisRepository()
    syn = repo.get_synthesis(args.synthesis_id)
    if not syn:
        print("Synthesis not found.")
        return 1
        
    gen = HypothesisGenerator()
    hyps = gen.generate_from_synthesis(syn)
    for h in hyps:
        print(f"Generated: {h.hypothesis_id} -> {h.hypothesis_text}")
    return 0
    
def run_hypothesis_approve(args) -> int:
    repo = SynthesisRepository()
    hyp = repo.get_hypothesis(args.id)
    if not hyp:
        print("Hypothesis not found.")
        return 1
    if hyp.status in [HypothesisStatus.TESTABLE, HypothesisStatus.REVIEW_REQUIRED]:
        hyp.status = HypothesisStatus.APPROVED_FOR_RESEARCH
        repo.save_hypothesis(hyp)
        print("Hypothesis approved for research (Phase 32 conversion).")
        return 0
    print(f"Cannot approve hypothesis in state: {hyp.status.value}")
    return 1
