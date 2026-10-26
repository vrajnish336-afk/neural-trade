import sys
import os

sys.path.insert(0, os.path.abspath("."))
from app.database.schema import init_db
from app.data.csv_provider import CsvHistoricalDataProvider
from datetime import datetime, timezone
from app.config import config
from app.research.robustness.runner import create_engine_factory
from app.backtesting.models import CostConfig
from app.diagnostics.telemetry import telemetry
from app.research.robustness.walk_forward import run_walk_forward_robustness

init_db()
provider = CsvHistoricalDataProvider("data/historical")
all_bars = []
for sym in ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT"]:
    for tf in ["1H"]:
        b = provider.get_historical_bars(sym, tf, datetime(2010, 1, 1, tzinfo=timezone.utc))
        b.sort(key=lambda x: x.timestamp)
        all_bars.extend(b[:int(len(b)*0.5)])
        
all_bars.sort(key=lambda x: x.timestamp)

config.MIN_SIGNAL_SCORE = 50.0
config.PAPER_TRADING = True
config.LIVE_TRADING = False
config.QUARANTINE_MEAN_REVERSION = True

def engine_factory():
    eng = create_engine_factory(use_adaptive=True, breakout_period=20)
    eng.cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.001)
    return eng

print("Running baseline manually to collect trades...")
window_size = 2000
step_size = 2000
total_bars = len(all_bars)
start_idx = 0

all_oos_trades = []

total_gross_profit = 0.0
total_gross_loss = 0.0
total_net_profit = 0.0
entry_fees = 0.0
exit_fees = 0.0
slippage_costs = 0.0
realized_portfolio_pnl = 0.0

breakout_trades = []
trend_trades = []
long_trades = []
short_trades = []

while start_idx + window_size <= total_bars:
    window_bars = all_bars[start_idx : start_idx + window_size]
    val_end_idx = int(window_size * 0.75)
    test_bars = window_bars[val_end_idx:]
    
    engine_test = engine_factory()
    res = engine_test.run(test_bars)
    
    for t in engine_test.closed_trades:
        all_oos_trades.append(t)
        if t.strategies and "Breakout" in t.strategies: breakout_trades.append(t)
        if t.strategies and "TrendFollowing" in t.strategies: trend_trades.append(t)
        if t.direction == "LONG": long_trades.append(t)
        if t.direction == "SHORT": short_trades.append(t)
        
        entry_fees += t.entry_cost
        exit_fees += t.exit_cost
        slippage_costs += t.slippage_cost
        
    total_gross_profit += res.gross_profit
    total_gross_loss += res.gross_loss
    total_net_profit += res.net_profit
    
    # Realized portfolio PnL per fold
    realized_portfolio_pnl += (res.final_equity - res.initial_capital)
        
    start_idx += step_size

print(f"TRADES: {len(all_oos_trades)}")
print(f"GP: {total_gross_profit}, GL: {total_gross_loss}")
print(f"Entry Fees: {entry_fees}, Exit Fees: {exit_fees}, Slippage: {slippage_costs}")
print(f"Sum of net trade PnL: {total_net_profit}")
print(f"Realized portfolio PnL: {realized_portfolio_pnl}")

def print_stats(name, trs):
    if not trs:
        print(f"{name}: 0 trades")
        return
    gp = sum(t.realized_pnl for t in trs if t.realized_pnl > 0)
    gl = abs(sum(t.realized_pnl for t in trs if t.realized_pnl <= 0))
    np = sum(t.realized_pnl for t in trs)
    wr = len([t for t in trs if t.realized_pnl > 0]) / len(trs)
    pf = gp/gl if gl > 0 else float('inf')
    exp = np/len(trs)
    print(f"{name}: {len(trs)} trades, WR: {wr:.2f}, GP: {gp:.2f}, GL: {gl:.2f}, NP: {np:.2f}, PF: {pf:.2f}, Exp: {exp:.2f}")

print_stats("Breakout", breakout_trades)
print_stats("Trend", trend_trades)
print_stats("LONG", long_trades)
print_stats("SHORT", short_trades)
