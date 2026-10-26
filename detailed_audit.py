import sys
import os

sys.path.insert(0, os.path.abspath("."))
from run_optimizer import evaluate_param
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
window_id = 1

total_trades = 0
total_wins = 0
total_losses = 0
total_gross_profit = 0.0
total_gross_loss = 0.0
total_fees_slippage = 0.0
total_net_profit = 0.0

fold_range = []

print("Running manual folds...")
while start_idx + window_size <= total_bars:
    window_bars = all_bars[start_idx : start_idx + window_size]
    
    train_end_idx = int(window_size * 0.5)
    val_end_idx = int(window_size * 0.75)
    
    test_bars = window_bars[val_end_idx:]
    
    engine_test = engine_factory()
    res = engine_test.run(test_bars)
    
    oos_trades = res.trades
    
    trades = res.number_of_trades
    wins = res.winning_trades
    losses = res.losing_trades
    gp = res.gross_profit
    gl = res.gross_loss
    np = res.net_profit
    pf = res.profit_factor
    dd = res.max_drawdown_pct
    
    # Calculate costs
    fees_slippage = sum(t.entry_cost + t.exit_cost + t.slippage_cost for t in oos_trades)
    
    exp = (np / trades) if trades > 0 else 0.0
    
    print(f"Fold {window_id}: PF={pf:.2f}, Exp=${exp:.2f}, DD={dd:.2f}%, trades={trades}, wins={wins}, losses={losses}, GP=${gp:.2f}, GL=${gl:.2f}, Fees/Slip=${fees_slippage:.2f}, NP=${np:.2f}")
    
    total_trades += trades
    total_wins += wins
    total_losses += losses
    total_gross_profit += gp
    total_gross_loss += gl
    total_fees_slippage += fees_slippage
    total_net_profit += np
    
    fold_range.append(window_id)
    
    start_idx += step_size
    window_id += 1

print("--- AGGREGATE ---")
print(f"Total Trades: {total_trades}")
print(f"Wins: {total_wins}, Losses: {total_losses}")
print(f"Total Gross Profit: ${total_gross_profit:.2f}")
print(f"Total Gross Loss: ${total_gross_loss:.2f}")
print(f"Total Net Profit: ${total_net_profit:.2f}")
print(f"Total Fees/Slippage: ${total_fees_slippage:.2f}")
agg_pf = total_gross_profit / total_gross_loss if total_gross_loss > 0 else 0
print(f"Aggregate PF: {agg_pf:.2f}")
agg_exp = total_net_profit / total_trades if total_trades > 0 else 0
print(f"Aggregate Expectancy: ${agg_exp:.2f}")

