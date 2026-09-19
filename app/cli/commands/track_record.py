import argparse
import logging
from app.database.schema import init_db
from app.research.track_record_service import PaperTrackRecordService

logger = logging.getLogger(__name__)

def setup_paper_track_parser(subparsers):
    parser = subparsers.add_parser("paper-track-records", help="List all paper track records")
    parser.set_defaults(func=run_list_tracks)
    
    obs_parser = subparsers.add_parser("paper-observations", help="List observations for a track record")
    obs_parser.add_argument("track_record_id", type=str)
    obs_parser.set_defaults(func=run_list_observations)

def run_list_tracks(args):
    init_db()
    service = PaperTrackRecordService()
    try:
        with service._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT track_record_id, current_health_state, current_equity, cumulative_return_pct, observation_count FROM paper_track_records ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            print("\n" + "="*80)
            print("PAPER TRACK RECORDS (LIVE TRADING DISABLED)")
            print("="*80)
            for r in rows:
                print(f"ID: {r[0][:8]}... | Health: {r[1]:<12} | Equity: ${r[2]:.2f} | Return: {r[3]:.2f}% | Obs: {r[4]}")
            print("="*80)
    except Exception as e:
        print(f"Error: {e}")
    return 0

def run_list_observations(args):
    init_db()
    service = PaperTrackRecordService()
    obs_list = service.get_observations(args.track_record_id)
    if not obs_list:
        print("No observations found.")
        return 1
        
    print("\n" + "="*80)
    print(f"OBSERVATIONS FOR TRACK RECORD: {args.track_record_id}")
    print("="*80)
    for obs in obs_list:
        print(f"Start: {obs.observation_start.strftime('%Y-%m-%d')} | End: {obs.observation_end.strftime('%Y-%m-%d')} | "
              f"PnL: ${obs.net_pnl:.2f} | Trades: {obs.trade_count} | Drift: {obs.drift_state}")
    print("="*80)
    return 0
