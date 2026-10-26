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

print("--- EVALUATING BASELINE ---")
baseline = evaluate_param(50.0, all_bars)
print(f"BASELINE: trades={baseline['total_trades']}, exp=${baseline['expectancy']:.2f}, pf={baseline['avg_pf']:.2f}, dd={baseline['avg_dd']:.2f}%")

candidates = [60.0, 70.0, 75.0, 80.0, 85.0]
results = []

for c in candidates:
    r = evaluate_param(c, all_bars)
    results.append(r)
    # FOR EVERY CANDIDATE REPORT INTERNALLY:
    # trades, wins/losses, PnL, expectancy, PF, max DD, minimum fold PF, minimum fold expectancy, median fold expectancy, severe-loss flag
    # PnL isn't explicitly returned, but expectancy * trades is roughly PnL (return_pct * 10000). Let's calculate from folds_data
    pnl = sum(f['ret'] * 100.0 for f in r['folds_data'])
    wins = sum(f['wins'] for f in r['folds_data'])
    losses = sum(f['losses'] for f in r['folds_data'])
    print(f"CANDIDATE MIN_SIGNAL_SCORE={c}:")
    print(f"trades: {r['total_trades']}")
    print(f"wins/losses: {wins}/{losses}")
    print(f"PnL: ${pnl:.2f}")
    print(f"expectancy: ${r['expectancy']:.2f}")
    print(f"PF: {r['avg_pf']:.2f}")
    print(f"max DD: {r['avg_dd']:.2f}%")
    print(f"minimum fold PF: {r['min_pf']:.2f}")
    print(f"minimum fold expectancy: ${r['min_exp']:.2f}")
    print(f"median fold expectancy: ${r['median_exp']:.2f}")
    print(f"severe-loss flag: {r['has_severe_loss']}")
    print("-" * 20)

valid = []
for r in results:
    if (
        r["total_trades"] >= 30
        and r["expectancy"] > 0
        and r["avg_dd"] < 30.0
        and not r["has_severe_loss"]
        and r.get("folds", 0) > 0
        and len(r.get("folds_data", [])) > 0
    ):
        valid.append(r)

if not valid:
    best = None
else:
    best = max(valid, key=lambda x: (x["expectancy"], x["avg_pf"]))

print("REPORT:")
print("STATUS: COMPLETED")
print(f"FOLDS: {baseline['folds']}")
print(f"PARAMETERS TESTED: MIN_SIGNAL_SCORE [{', '.join(map(str, candidates))}]")
print(f"VALID CANDIDATES: {len(valid)}")
print(f"REJECTED CANDIDATES: {len(results) - len(valid)}")
print(f"BASELINE PF/EXP/DD: {baseline['avg_pf']:.2f} / ${baseline['expectancy']:.2f} / {baseline['avg_dd']:.2f}%")

if best:
    print(f"BEST VALID PROPOSAL: MIN_SIGNAL_SCORE = {best['min_score']}")
    print(f"PROPOSAL PF/EXP/DD: {best['avg_pf']:.2f} / ${best['expectancy']:.2f} / {best['avg_dd']:.2f}%")
    print(f"TRADE COUNT: {best['total_trades']}")
    print(f"MIN FOLD PF: {best['min_pf']:.2f}")
    print(f"MIN FOLD EXPECTANCY: ${best['min_exp']:.2f}")
    worst_fold = min(best['folds_data'], key=lambda f: f['pf'])
    print(f"WORST FOLD: Fold {worst_fold['id']} (PF={worst_fold['pf']:.2f})")
else:
    print("BEST VALID PROPOSAL: NO VALID PROPOSAL")
    print("PROPOSAL PF/EXP/DD: N/A")
    print("TRADE COUNT: N/A")
    print("MIN FOLD PF: N/A")
    print("MIN FOLD EXPECTANCY: N/A")
    print("WORST FOLD: N/A")

print("FINAL OOS TOUCHED: NO")
print("AUTO-APPLIED: NO")
print("NEXT ACTION: Await review of proposal")
