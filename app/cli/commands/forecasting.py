import argparse
import sys
import json
from datetime import datetime
from app.forecasting.service import ForecastingService
from app.forecasting.repository import ForecastRepository

def setup_forecasting_parser(subparsers):
    parser = subparsers.add_parser("forecast", help="Generate a price trajectory forecast (PAPER/RESEARCH ONLY)")
    parser.add_argument("symbol", help="Symbol to forecast")
    parser.add_argument("--timeframe", default="1D")
    parser.add_argument("--window", type=int, default=100, help="Input window size")
    parser.add_argument("--horizon", type=int, default=10, help="Prediction horizon")
    parser.add_argument("--model", default="baseline", choices=["baseline", "kronos"], help="Model choice")
    parser.set_defaults(func=run_forecast)
    
    hist_parser = subparsers.add_parser("forecast-history", help="View forecast history")
    hist_parser.add_argument("--symbol")
    hist_parser.set_defaults(func=run_forecast_history)

def _print_safety_banner():
    print("==================================================")
    print("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    print("FORECAST != TRADING SIGNAL.")
    print("==================================================\n")

def run_forecast(args) -> int:
    _print_safety_banner()
    svc = ForecastingService()
    
    # Check if kronos was requested and warn if missing
    if args.model == "kronos" and not svc.advanced.is_available():
        print("WARNING: Kronos adapter unavailable in current environment. PyTorch/Chronos missing.")
        print("Falling back to Baseline.\n")
        args.model = "baseline"
        
    record = svc.generate_forecast(args.symbol, args.timeframe, args.window, args.horizon, args.model)
    if not record:
        print("Failed to generate forecast.")
        return 1
        
    print(f"Forecast ID: {record.forecast_id}")
    print(f"Model: {record.model_name}")
    print(f"Symbol: {record.symbol} | Horizon: {record.forecast_horizon}")
    print(f"Status: {record.status}")
    print("\nPredicted Trajectory:")
    preds = json.loads(record.predicted_values_json)
    for i, val in enumerate(preds):
        print(f"  T+{i+1}: {val:.2f}")
    return 0

def run_forecast_history(args) -> int:
    _print_safety_banner()
    repo = ForecastRepository()
    records = repo.get_records(args.symbol)
    
    if not records:
        print("No forecasts found.")
        return 0
        
    print(f"{'ID':<36} | {'SYMBOL':<10} | {'MODEL':<20} | {'HORIZON':<8} | {'MAE':<10} | {'DIR_ACC':<10}")
    print("-" * 105)
    for r in records:
        mae = f"{r.mae:.4f}" if r.mae is not None else "N/A"
        acc = f"{r.directional_accuracy:.2f}" if r.directional_accuracy is not None else "N/A"
        print(f"{r.forecast_id:<36} | {r.symbol:<10} | {r.model_name[:20]:<20} | {r.forecast_horizon:<8} | {mae:<10} | {acc:<10}")
    return 0
