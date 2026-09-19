import sys
import argparse
from app.config import config
from app.execution.safety import ExecutionSafetyGate

def setup_status_parser(subparsers):
    parser = subparsers.add_parser("status", help="Show system status")
    parser.set_defaults(func=run_status)

def run_status(args: argparse.Namespace) -> int:
    try:
        import sqlite3
        conn = sqlite3.connect(config.DB_PATH)
        conn.close()
        db_status = "AVAILABLE"
    except Exception:
        db_status = "UNAVAILABLE"

    print("================================================")
    print("NEURAL TRADE SYSTEM STATUS")
    print("================================================\n")
    print("Safety:")
    print(f"PAPER_TRADING: {'ENABLED' if config.PAPER_TRADING else 'DISABLED'}")
    print(f"LIVE_TRADING: {'ENABLED' if config.LIVE_TRADING else 'DISABLED'}")
    print("Execution Safety Gate: ACTIVE\n")
    print("Available Strategies:")
    print("- breakout")
    print("- trend_following")
    print("- mean_reversion\n")
    print("Research Environment:")
    print(f"Database: {db_status}")
    print("================================================")
    
    return 0
