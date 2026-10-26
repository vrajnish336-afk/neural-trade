import sys
import os

sys.path.insert(0, os.path.abspath("."))
from run_optimizer import evaluate_param
from app.database.schema import init_db
from app.data.csv_provider import CsvHistoricalDataProvider
from datetime import datetime, timezone

init_db()
provider = CsvHistoricalDataProvider("data/historical")
all_bars = []
for sym in ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT"]:
    for tf in ["1H"]:
        b = provider.get_historical_bars(sym, tf, datetime(2010, 1, 1, tzinfo=timezone.utc))
        b.sort(key=lambda x: x.timestamp)
        all_bars.extend(b[:int(len(b)*0.5)])
        
all_bars.sort(key=lambda x: x.timestamp)

print("Running baseline...")
baseline = evaluate_param(50.0, all_bars)

folds = baseline["folds_data"]
total_trades = sum(f["trades"] for f in folds)

print("TOTAL_TRADES:", total_trades)
print("TRADES_PER_FOLD:", [f["trades"] for f in folds])
print("WINS_PER_FOLD:", [f["wins"] for f in folds])
print("LOSSES_PER_FOLD:", [f["losses"] for f in folds])
print("PF_PER_FOLD:", [round(f["pf"],2) for f in folds])
print("EXP_PER_FOLD:", [round(f["expectancy"],2) for f in folds])
print("DD_PER_FOLD:", [round(f["dd"],2) for f in folds])

# Find how the PF and Expectancy are calculated
# Need to examine run_walk_forward_robustness output.
