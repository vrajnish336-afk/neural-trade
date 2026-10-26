import sys
import os
from collections import defaultdict

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

long_trades = []
short_trades = []
breakout_longs = []
trend_longs = []

sl_exits = 0
tp_exits = 0
other_exits = 0

long_holding_times = []
long_pre_cost = 0.0
long_fees = 0.0
long_slippage = 0.0
long_post_cost = 0.0

while start_idx + window_size <= total_bars:
    window_bars = all_bars[start_idx : start_idx + window_size]
    val_end_idx = int(window_size * 0.75)
    test_bars = window_bars[val_end_idx:]
    
    engine_test = engine_factory()
    res = engine_test.run(test_bars)
    
    for t in engine_test.closed_trades:
        if t.direction == "LONG":
            long_trades.append(t)
            if t.strategies and "Breakout" in t.strategies: breakout_longs.append(t)
            if t.strategies and "TrendFollowing" in t.strategies: trend_longs.append(t)
            
            # parse reason
            r = t.exit_reason.upper() if t.exit_reason else ""
            if "SL" in r or "STOP" in r:
                sl_exits += 1
            elif "TP" in r or "TAKE" in r or "PROFIT" in r:
                tp_exits += 1
            else:
                other_exits += 1
                
            holding_time = (t.exit_time - t.entry_time).total_seconds() / 3600 # hours
            long_holding_times.append(holding_time)
            
            long_post_cost += t.realized_pnl
            fees = t.entry_cost + t.exit_cost
            slip = t.slippage_cost
            long_fees += fees
            long_slippage += slip
            long_pre_cost += (t.realized_pnl + fees + slip)
            
        elif t.direction == "SHORT":
            short_trades.append(t)
            
    start_idx += step_size

print(f"LONG TRADES: {len(long_trades)}")
print(f"SHORT TRADES: {len(short_trades)}")
print(f"LONG PRE-COST PNL: {long_pre_cost:.2f}")
print(f"LONG FEES: {long_fees:.2f}")
print(f"LONG SLIPPAGE: {long_slippage:.2f}")
print(f"LONG POST-COST PNL: {long_post_cost:.2f}")
print(f"LONG EXITS: SL={sl_exits}, TP={tp_exits}, OTHER={other_exits}")

avg_ht = sum(long_holding_times)/len(long_holding_times) if long_holding_times else 0
print(f"AVG LONG HOLDING TIME: {avg_ht:.2f} hours")
print(f"LONG Breakouts: {len(breakout_longs)}")
print(f"LONG Trends: {len(trend_longs)}")
