import argparse
import logging
import json
from app.database.schema import init_db
from app.research.decision_engine import ResearchDecisionEngine
from app.research.decision_models import ResearchRelationship, RelationshipType

logger = logging.getLogger(__name__)

def setup_research_decision_parser(subparsers):
    eval_parser = subparsers.add_parser("research-evaluate", help="Evaluate accumulated evidence for an identity hash")
    eval_parser.add_argument("identity_hash", type=str, help="Research Identity Hash")
    eval_parser.set_defaults(func=run_research_evaluate)
    
    conc_parser = subparsers.add_parser("research-conclusion", help="View a specific Research Conclusion")
    conc_parser.add_argument("conclusion_id", type=str, help="Conclusion ID")
    conc_parser.set_defaults(func=run_research_conclusion)
    
    conf_parser = subparsers.add_parser("research-conflicts", help="View unresolved research conflicts")
    conf_parser.set_defaults(func=run_research_conflicts)
    
    rel_parser = subparsers.add_parser("research-relationships", help="View research relationships")
    rel_parser.set_defaults(func=run_research_relationships)

def run_research_evaluate(args):
    init_db()
    engine = ResearchDecisionEngine()
    conc = engine.evaluate_identity(args.identity_hash)
    
    if not conc:
        print(f"No completed experiments found for identity {args.identity_hash}.")
        return 1
        
    print("\n--- RESEARCH CONCLUSION GENERATED ---")
    print(f"Conclusion ID : {conc.conclusion_id}")
    print(f"Decision State: {conc.decision_state.value}")
    print(f"Confidence    : {conc.confidence_state.value}")
    print(f"Summary       : {conc.summary}")
    print(f"Next Action   : {conc.next_research_action.value}")
    print(f"Supporting Exps: {conc.supporting_evidence_count} | Conflicting: {conc.conflicting_evidence_count}")
    return 0

def run_research_conclusion(args):
    init_db()
    engine = ResearchDecisionEngine()
    try:
        with engine._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM research_conclusions WHERE conclusion_id = ?", (args.conclusion_id,))
            row = cursor.fetchone()
            if not row:
                print(f"Conclusion {args.conclusion_id} not found.")
                return 1
            print(f"Conclusion ID : {row[0]}")
            print(f"Identity Hash : {row[1]}")
            print(f"Decision State: {row[2]}")
            print(f"Confidence    : {row[3]}")
            print(f"Summary       : {row[4]}")
            print(f"Next Action   : {row[8]}")
            print(f"Provenance    : {row[10]}")
    except Exception as e:
        print(f"Error: {e}")
    return 0

def run_research_conflicts(args):
    init_db()
    engine = ResearchDecisionEngine()
    try:
        with engine._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT conflict_id, identity_hash, conflict_type, severity, explanation FROM research_conflicts WHERE resolution_status='UNRESOLVED'")
            rows = cursor.fetchall()
            print("\n--- UNRESOLVED RESEARCH CONFLICTS ---")
            for r in rows:
                print(f"[{r[0][:8]}] Hash: {r[1][:8]} | Type: {r[2]} ({r[3]})")
                print(f"  Explanation: {r[4]}")
    except Exception as e:
        print(f"Error: {e}")
    return 0

def run_research_relationships(args):
    init_db()
    engine = ResearchDecisionEngine()
    try:
        with engine._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT source_id, target_id, relationship_type, description FROM research_relationships LIMIT 50")
            rows = cursor.fetchall()
            print("\n--- RESEARCH RELATIONSHIPS ---")
            for r in rows:
                print(f"{r[0][:8]} --[{r[2]}]--> {r[1][:8]} ({r[3]})")
    except Exception as e:
        print(f"Error: {e}")
    return 0
