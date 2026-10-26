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
config.DIAGNOSTIC_MODE = True
telemetry.enabled = True
telemetry.reset()

def engine_factory():
    eng = create_engine_factory(use_adaptive=True, breakout_period=20)
    eng.cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.001)
    return eng

print("Running baseline with telemetry...")
run_walk_forward_robustness(
    bars=all_bars,
    engine_factory=engine_factory,
    window_size=2000,
    step_size=2000
)

snap = telemetry.export_snapshot()

print("--- TELEMETRY SNAPSHOT ---")
print("stage_counts:", snap["stage_counts"])
print("rejection_counts:", snap["rejection_counts"])
print("strategy_evaluations:", snap["strategy_evaluations"])
print("strategy_signals_long:", snap["strategy_signals_long"])
print("strategy_signals_short:", snap["strategy_signals_short"])
print("regime_counts:", snap["regime_counts"])
