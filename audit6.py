import sys
import os
from collections import defaultdict
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

long_trades = []
other_exits = defaultdict(int)
risk_blocks = []

while start_idx + window_size <= total_bars:
    window_bars = all_bars[start_idx : start_idx + window_size]
    val_end_idx = int(window_size * 0.75)
    test_bars = window_bars[val_end_idx:]
    
    engine_test = engine_factory()
    res = engine_test.run(test_bars)
    
    for t in engine_test.closed_trades:
        if t.direction == "LONG":
            long_trades.append(t)
            r = t.exit_reason.upper() if t.exit_reason else ""
            if not ("SL" in r or "STOP" in r or "TP" in r or "TAKE" in r or "PROFIT" in r):
                other_exits[t.exit_reason] += 1
                
    # To analyze risk blocks we can look at the telemetry or rejected signals
    # We don't have direct access to rejected signals unless the engine stores them
    if hasattr(engine_test, 'rejected_signals'):
        for s, reason in engine_test.rejected_signals:
            if "Risk" in reason or "limit" in reason.lower():
                risk_blocks.append((s, reason))
            
    start_idx += step_size

print(f"LONG TRADES: {len(long_trades)}")
print(f"OTHER EXITS:")
for k, v in other_exits.items():
    print(f"  {k}: {v}")
    
# Breakout exhaustion - we can't easily get the EMA at the exact time without re-running indicators,
# but we know it's breakout if the entry was hitting highs.
# Actually we can just print the risk blocks count
print(f"RISK BLOCKS CAPTURED: {len(risk_blocks)}")
