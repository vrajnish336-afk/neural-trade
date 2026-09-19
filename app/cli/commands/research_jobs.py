import argparse
import logging
from app.database.schema import init_db
from app.research.orchestrator_service import ResearchJobOrchestrator
from app.research.orchestrator_models import OrchestratorConfig
from app.research.opportunity_intelligence import OpportunityIntelligence

logger = logging.getLogger(__name__)

def setup_research_jobs_parser(subparsers):
    # Command to run a single cycle
    cycle_parser = subparsers.add_parser("research-cycle", help="Execute one Continuous Research Orchestration cycle (Phase 15)")
    cycle_parser.set_defaults(func=run_research_cycle)
    
    # Command to view jobs
    jobs_parser = subparsers.add_parser("research-jobs", help="View Research Jobs Queue")
    jobs_parser.set_defaults(func=run_research_jobs)

def run_research_cycle(args):
    init_db()
    print("Starting Research Orchestration Cycle...")
    
    # First, let's just make sure unmapped AI analyses become opportunities
    intel = OpportunityIntelligence()
    
    # We borrow the logic from old loop_orchestrator to map hypotheses -> opportunities 
    # (or we can just put it here since it's the gateway)
    try:
        from app.research.loop_repository import ResearchLoopRepository
        repo = ResearchLoopRepository()
        with repo._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.analysis_id, a.article_id, a.research_hypothesis, a.affected_symbols, a.evidence_type
                FROM ai_research_analysis a
                WHERE a.evidence_type = 'RESEARCH_HYPOTHESIS'
                AND a.analysis_id NOT IN (SELECT source_analysis_id FROM research_opportunities)
            """)
            rows = cursor.fetchall()
            
            import json
            from app.research.ai_models import EvidenceType
            count = 0
            for row in rows:
                class MockAnalysis:
                    analysis_id = row[0]
                    article_id = row[1]
                    research_hypothesis = row[2]
                    affected_symbols = json.loads(row[3]) if row[3] else []
                    evidence_type = EvidenceType(row[4])
                if intel.evaluate_analysis(MockAnalysis()):
                    count += 1
            print(f"Evaluated {count} new AI hypotheses into Opportunities.")
    except Exception as e:
        print(f"Error evaluating opportunities: {e}")

    # Now run the actual job orchestrator cycle
    orchestrator = ResearchJobOrchestrator(orchestrator_config=OrchestratorConfig(
        enabled=True, max_queue_size=100, max_jobs_per_cycle=5, max_retries=3
    ))
    
    executed = orchestrator.run_cycle()
    print(f"Executed/Claimed {executed} jobs in this cycle.")
    
    return 0

def run_research_jobs(args):
    init_db()
    orchestrator = ResearchJobOrchestrator()
    try:
        with orchestrator.memory_repo._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT state, COUNT(*) FROM research_jobs GROUP BY state
            """)
            counts = cursor.fetchall()
            print("\n--- RESEARCH JOBS QUEUE ---")
            for c in counts:
                print(f"{c[0]}: {c[1]}")
                
            print("\nActive/Recent Jobs:")
            cursor.execute("""
                SELECT job_id, state, priority, retry_count, failure_reason 
                FROM research_jobs 
                ORDER BY created_at DESC LIMIT 10
            """)
            rows = cursor.fetchall()
            for r in rows:
                print(f"[{r[0][:8]}] State: {r[1]} | Priority: {r[2]} | Retries: {r[3]}")
                if r[4]:
                    print(f"  Reason: {r[4]}")
    except Exception as e:
        print(f"Error viewing jobs: {e}")
    return 0
