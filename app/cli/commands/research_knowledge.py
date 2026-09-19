import argparse
import logging
import json
from app.database.schema import init_db
from app.research.knowledge_service import ResearchKnowledgeService

logger = logging.getLogger(__name__)

def setup_research_knowledge_parser(subparsers):
    know_parser = subparsers.add_parser("research-knowledge", help="View unified knowledge snapshot for an identity")
    know_parser.add_argument("identity_hash", type=str, help="Research Identity Hash")
    know_parser.set_defaults(func=run_research_knowledge)
    
    gaps_parser = subparsers.add_parser("knowledge-gaps", help="View all open evidence gaps")
    gaps_parser.set_defaults(func=run_knowledge_gaps)
    
    hist_parser = subparsers.add_parser("knowledge-history", help="View knowledge change history for an identity")
    hist_parser.add_argument("identity_hash", type=str, help="Research Identity Hash")
    hist_parser.set_defaults(func=run_knowledge_history)

def run_research_knowledge(args):
    init_db()
    service = ResearchKnowledgeService()
    snap = service.get_snapshot(args.identity_hash)
    
    if not snap:
        print(f"No knowledge found for identity {args.identity_hash}.")
        return 1
        
    print("\n" + "="*50)
    print("RESEARCH KNOWLEDGE SNAPSHOT")
    print("="*50)
    print(f"Identity     : {snap.identity_hash}")
    print(f"Hypothesis   : {snap.canonical_hypothesis[:100]}...")
    print(f"Symbols      : {snap.affected_symbols}")
    print(f"Strategy     : {snap.mapped_strategy}")
    print("-" * 50)
    print(f"Experiments  : {snap.total_completed_jobs} completed out of {snap.total_experiments} total")
    print(f"Decision     : {snap.current_decision_state.value}")
    print(f"Confidence   : {snap.current_confidence_state.value}")
    print(f"Next Action  : {snap.next_research_action.value}")
    print("-" * 50)
    print(f"Open Gaps    : {len(snap.open_evidence_gaps)}")
    for g in snap.open_evidence_gaps:
        print(f"  - [{g.severity}] {g.gap_type.value} -> {g.recommended_action.value}")
    print(f"Conflicts    : {len(snap.unresolved_conflicts)}")
    for c in snap.unresolved_conflicts:
        print(f"  - {c.conflict_type} between {c.experiment_id_1[:8]} and {c.experiment_id_2[:8]}")
    print("="*50)
    return 0

def run_knowledge_gaps(args):
    init_db()
    service = ResearchKnowledgeService()
    try:
        with service._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT identity_hash, gap_type, severity, recommended_action FROM research_evidence_gaps WHERE status='OPEN'")
            rows = cursor.fetchall()
            print("\n--- OPEN EVIDENCE GAPS ---")
            for r in rows:
                print(f"Hash: {r[0][:8]} | [{r[2]}] {r[1]} -> Action: {r[3]}")
    except Exception as e:
        print(f"Error: {e}")
    return 0

def run_knowledge_history(args):
    init_db()
    service = ResearchKnowledgeService()
    try:
        with service._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_at, change_type, previous_decision, new_decision, reason FROM research_knowledge_changes WHERE identity_hash=? ORDER BY created_at ASC", (args.identity_hash,))
            rows = cursor.fetchall()
            print("\n--- KNOWLEDGE HISTORY ---")
            for r in rows:
                print(f"[{r[0]}] {r[1]}")
                if r[2] != r[3]:
                    print(f"  Decision changed: {r[2]} -> {r[3]}")
                print(f"  Reason: {r[4]}")
    except Exception as e:
        print(f"Error: {e}")
    return 0
