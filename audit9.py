import sys
import os
import statistics

sys.path.insert(0, os.path.abspath("."))
from app.database.schema import init_db
from app.data.csv_provider import CsvHistoricalDataProvider
from datetime import datetime, timezone
from app.config import config
from app.research.robustness.runner import create_engine_factory
from app.backtesting.models import CostConfig

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

closed_trades = []
unresolved_hts = []
long_hts = []
short_hts = []

b_l_pnl, b_s_pnl, t_l_pnl, t_s_pnl = 0, 0, 0, 0

while start_idx + window_size <= total_bars:
    window_bars = all_bars[start_idx : start_idx + window_size]
    val_end_idx = int(window_size * 0.75)
    test_bars = window_bars[val_end_idx:]
    
    engine_test = engine_factory()
    res = engine_test.run(test_bars)
    
    closed_trades.extend(res.trades)
    
    fold_end_time = test_bars[-1].timestamp
    for p in engine_test.portfolio.state.open_positions:
        ht = (fold_end_time - p['entry_time']).total_seconds() / 3600
        unresolved_hts.append(ht)
        if p['direction'] == 'LONG': long_hts.append(ht)
        else: short_hts.append(ht)
        
    for t in res.trades:
        ht = (t.exit_time - t.entry_time).total_seconds() / 3600
        if t.direction == 'LONG': long_hts.append(ht)
        else: short_hts.append(ht)
        
        s = t.strategies or ""
        if "Breakout" in s and t.direction == "LONG": b_l_pnl += t.realized_pnl
        if "Breakout" in s and t.direction == "SHORT": b_s_pnl += t.realized_pnl
        if "TrendFollowing" in s and t.direction == "LONG": t_l_pnl += t.realized_pnl
        if "TrendFollowing" in s and t.direction == "SHORT": t_s_pnl += t.realized_pnl
            
    start_idx += step_size

cl_hts = [(t.exit_time - t.entry_time).total_seconds()/3600 for t in closed_trades]

def stats(hts):
    if not hts: return 0, 0
    return statistics.median(hts), sum(hts)/len(hts)

cl_med, cl_avg = stats(cl_hts)
ur_med, ur_avg = stats(unresolved_hts)
l_med, l_avg = stats(long_hts)
s_med, s_avg = stats(short_hts)

print(f"CLOSED HT: Med {cl_med:.1f}h, Avg {cl_avg:.1f}h")
print(f"UNRESOLVED HT: Med {ur_med:.1f}h, Avg {ur_avg:.1f}h")
print(f"LONG HT: Med {l_med:.1f}h, Avg {l_avg:.1f}h")
print(f"SHORT HT: Med {s_med:.1f}h, Avg {s_avg:.1f}h")
print(f"B L PNL: {b_l_pnl:.2f}, B S PNL: {b_s_pnl:.2f}")
print(f"T L PNL: {t_l_pnl:.2f}, T S PNL: {t_s_pnl:.2f}")
