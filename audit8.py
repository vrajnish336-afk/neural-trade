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

window_size = 2000
step_size = 2000
total_bars = len(all_bars)
start_idx = 0

all_closed_trades = []
total_unresolved = 0
total_unrealized_mtm = 0.0

while start_idx + window_size <= total_bars:
    window_bars = all_bars[start_idx : start_idx + window_size]
    val_end_idx = int(window_size * 0.75)
    test_bars = window_bars[val_end_idx:]
    
    engine_test = engine_factory()
    res = engine_test.run(test_bars)
    
    all_closed_trades.extend(res.trades)
    total_unresolved += res.unresolved_positions_count
    total_unrealized_mtm += res.unrealized_mtm
            
    start_idx += step_size

# Telemetry snapshot
snap = telemetry.export_snapshot()
stages = snap.get("pipeline_stages", {})
rejections = snap.get("rejection_reasons", {})

# Computations
wins = len([t for t in all_closed_trades if t.realized_pnl > 0])
losses = len([t for t in all_closed_trades if t.realized_pnl <= 0])
total_closed = wins + losses
win_rate = wins / total_closed if total_closed > 0 else 0

gp = sum(t.realized_pnl for t in all_closed_trades if t.realized_pnl > 0)
gl = abs(sum(t.realized_pnl for t in all_closed_trades if t.realized_pnl <= 0))
realized_pnl = gp - gl
pf = gp / gl if gl > 0 else float('inf')
expectancy = realized_pnl / total_closed if total_closed > 0 else 0

long_trades = [t for t in all_closed_trades if t.direction == "LONG"]
short_trades = [t for t in all_closed_trades if t.direction == "SHORT"]

long_pnl = sum(t.realized_pnl for t in long_trades)
short_pnl = sum(t.realized_pnl for t in short_trades)

strat_stats = {"Breakout LONG": 0, "Breakout SHORT": 0, "TrendFollowing LONG": 0, "TrendFollowing SHORT": 0}
for t in all_closed_trades:
    if t.strategies:
        s = t.strategies
        key = None
        if "Breakout" in s and t.direction == "LONG": key = "Breakout LONG"
        if "Breakout" in s and t.direction == "SHORT": key = "Breakout SHORT"
        if "TrendFollowing" in s and t.direction == "LONG": key = "TrendFollowing LONG"
        if "TrendFollowing" in s and t.direction == "SHORT": key = "TrendFollowing SHORT"
        if key: strat_stats[key] += 1

print(f"EVALUATIONS: {stages.get('MARKET_BARS', 0)}")
print(f"ENTRIES: {stages.get('PAPER_TRADES', 0) + total_closed + total_unresolved}") # approx 
print(f"CLOSED: {total_closed}")
print(f"UNRESOLVED: {total_unresolved}")
print(f"WIN/LOSS: {wins}/{losses}")
print(f"WIN RATE: {win_rate*100:.2f}%")
print(f"REALIZED PNL: {realized_pnl:.2f}")
print(f"TERMINAL MTM: {total_unrealized_mtm:.2f}")
print(f"PF: {pf:.2f}")
print(f"EXPECTANCY: {expectancy:.2f}")
print(f"LONG VS SHORT: L: {len(long_trades)} trades ({long_pnl:.2f}), S: {len(short_trades)} trades ({short_pnl:.2f})")
print(f"STRATEGY ATTRIBUTION: {strat_stats}")

print("REJECTIONS:")
for k, v in rejections.items():
    print(f"  {k}: {v}")
