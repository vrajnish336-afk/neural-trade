import logging
from typing import List
from datetime import datetime, timezone
import warnings

from app.config import config
from app.database.schema import init_db
from app.research.robustness.runner import create_engine_factory
from app.research.robustness.walk_forward import run_walk_forward_robustness
from app.backtesting.models import CostConfig

warnings.filterwarnings('ignore')
logging.getLogger("app.backtesting.engine").setLevel(logging.WARNING)

def run():
    init_db()
    from app.data.csv_provider import CsvHistoricalDataProvider
    provider = CsvHistoricalDataProvider("data/historical")
    all_bars = []
    for sym in ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT"]:
        for tf in ["1H"]:
            b = provider.get_historical_bars(sym, tf, datetime(2010, 1, 1, tzinfo=timezone.utc))
            b.sort(key=lambda x: x.timestamp)
            all_bars.extend(b[:int(len(b)*0.5)])
            
    all_bars.sort(key=lambda x: x.timestamp)
    
    config.MIN_SIGNAL_SCORE = 85.0
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False
    config.QUARANTINE_MEAN_REVERSION = True
    
    def engine_factory():
        eng = create_engine_factory(use_adaptive=True, breakout_period=20)
        eng.cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.001)
        return eng
        
    wf_results = run_walk_forward_robustness(
        bars=all_bars,
        engine_factory=engine_factory,
        window_size=2000,
        step_size=2000
    )
    
    for i, r in enumerate(wf_results):
        print(f"FOLD {i+1}: Trades={r.trades}, PF={r.profit_factor:.2f}, Ret={r.return_pct:.2f}%, DD={r.max_drawdown_pct:.2f}%")
        
        # Need to know the expectancy inside this fold
        exp = ((r.return_pct / 100.0) * 10000.0) / r.trades if r.trades > 0 else 0
        print(f"   Expectancy=${exp:.2f}")

if __name__ == "__main__":
    run()
