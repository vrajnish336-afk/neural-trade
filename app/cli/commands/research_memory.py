import argparse
import logging
import json
from app.database.schema import init_db
from app.research.memory_repository import ResearchMemoryRepository

logger = logging.getLogger(__name__)

def setup_research_memory_parser(subparsers):
    mem_parser = subparsers.add_parser("research-memory", help="View Research Memory")
    mem_parser.set_defaults(func=run_research_memory)
    
    opp_parser = subparsers.add_parser("opportunities", help="View Research Opportunities")
    opp_parser.set_defaults(func=run_opportunities)
    
    opp_id_parser = subparsers.add_parser("opportunity", help="View specific Opportunity")
    opp_id_parser.add_argument("id", type=str, help="Opportunity ID")
    opp_id_parser.set_defaults(func=run_opportunity)

def run_research_memory(args):
    init_db()
    repo = ResearchMemoryRepository()
    try:
        with repo._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT identity_hash, mapped_strategy, affected_symbols, latest_conclusion FROM research_memory LIMIT 20")
            rows = cursor.fetchall()
            print("\n--- RESEARCH MEMORY ---")
            for r in rows:
                print(f"[{r[0][:8]}] {r[1]} on {r[2]} -> {r[3] or 'NO_CONCLUSION'}")
    except Exception as e:
        print(f"Error: {e}")
    return 0

def run_opportunities(args):
    init_db()
    repo = ResearchMemoryRepository()
    try:
        opps = repo.get_unresolved_opportunities(limit=10)
        print("\n--- RESEARCH OPPORTUNITIES ---")
        if not opps:
            print("No pending opportunities found.")
        for opp in opps:
            print(f"[{opp.opportunity_id}] Priority: {opp.research_priority:.2f} | Status: {opp.status.value}")
            print(f"  Strategy: {opp.mapped_strategy} | Symbols: {opp.affected_symbols}")
            print(f"  Reason: {opp.reason}")
    except Exception as e:
        print(f"Error: {e}")
    return 0

def run_opportunity(args):
    init_db()
    repo = ResearchMemoryRepository()
    try:
        with repo._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM research_opportunities WHERE opportunity_id = ?", (args.id,))
            row = cursor.fetchone()
            if not row:
                print(f"Opportunity {args.id} not found.")
                return 1
            print(f"Opportunity: {row[0]}")
            print(f"Priority: {row[10]:.2f}")
            print(f"Status: {row[11]}")
            print(f"Reason: {row[12]}")
            print(f"Hypothesis: {row[3]}")
    except Exception as e:
        print(f"Error: {e}")
    return 0
