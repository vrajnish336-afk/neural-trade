import argparse
from app.services.observability import ObservabilityService

def setup_analyze_parser(subparsers):
    parser = subparsers.add_parser("analyze", help="Analyze a backtest run or research experiment")
    parser.add_argument("run_id", help="The ID of the run to analyze")
    parser.set_defaults(func=run_analyze)

def run_analyze(args: argparse.Namespace) -> int:
    report = ObservabilityService.get_analytics_report(args.run_id)
    
    if not report:
        print(f"Error: Analytics report not found for run_id '{args.run_id}'")
        return 1
        
    print("================================================")
    print("NEURAL TRADE — RESEARCH OBSERVABILITY")
    print("================================================")
    print(f"\nRun ID: {report.backtest_id}\n")
    
    print("--- EXECUTION FRICTION ---")
    print(ObservabilityService.format_friction(report))
    
    print("--- METRICS ---")
    tm = report.trade_metrics
    em = report.equity_metrics
    print(f"Total Trades: {tm.total_trades}")
    print(f"Win Rate: {tm.win_rate:.2f}%")
    print(f"Profit Factor: {tm.profit_factor:.2f}")
    print(f"Max Drawdown: {em.max_drawdown_pct:.2f}%\n")
    
    print("--- TELEMETRY FUNNEL ---")
    print(ObservabilityService.format_funnel(report))
    print("\n--- REGIME ATTRIBUTION ---")
    print(ObservabilityService.format_regimes(report))
    
    print("\n================================================")
    return 0
