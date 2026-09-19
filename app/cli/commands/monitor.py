import argparse
import logging
from app.database.schema import init_db
from app.research.monitoring_service import PaperMonitoringService

logger = logging.getLogger(__name__)

def setup_paper_monitor_parser(subparsers):
    parser = subparsers.add_parser("paper-monitor", help="Run the Paper Monitoring Cycle")
    parser.set_defaults(func=run_paper_monitor)

def run_paper_monitor(args):
    init_db()
    service = PaperMonitoringService()
    try:
        print("\n" + "="*80)
        print("PAPER MONITORING CYCLE (LIVE TRADING DISABLED)")
        print("="*80)
        
        result = service.run_cycle()
        
        print(f"Status:                 {result.status}")
        print(f"Cycle ID:               {result.cycle_id}")
        print(f"Validations discovered: {result.validations_discovered}")
        print(f"Observations recorded:  {result.observations_recorded}")
        print(f"Duplicates skipped:     {result.duplicates_skipped}")
        print(f"Health transitions:     {result.health_transitions}")
        print(f"Opportunities created:  {result.opportunities_created}")
        print(f"Knowledge changes:      {result.knowledge_updates}")
        print(f"Errors:                 {result.errors}")
        
        if result.error_messages:
            print("\nErrors:")
            for e in result.error_messages:
                print(f" - {e}")
                
        print("="*80)
    except Exception as e:
        print(f"Error executing cycle: {e}")
    return 0
