import logging
from collections import defaultdict
from app.config import config
from app.database.schema import init_db
from app.research.dataset import generate_synthetic_data, generate_regime_dataset
from app.research.robustness.runner import create_engine_factory

logging.getLogger("app.backtesting.engine").setLevel(logging.WARNING)

def run():
    init_db()
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False
    config.QUARANTINE_MEAN_REVERSION = True

    symbols = ["OPT_BTC", "OPT_ETH", "OPT_SOL", "OPT_BNB"]
    
    all_bars = []
    
    for symbol in symbols:
        bars = generate_synthetic_data([symbol], 2000, seed=42)[symbol]
        all_bars.extend(bars)
        bars = generate_regime_dataset("TRENDING_UP", symbol, 1000, seed=1)
        all_bars.extend(bars)
        bars = generate_regime_dataset("TRENDING_DOWN", symbol, 1000, seed=2)
        all_bars.extend(bars)
        bars = generate_regime_dataset("HIGH_VOLATILITY", symbol, 1000, seed=3)
        all_bars.extend(bars)
        
    # We must run each asset sequentially to avoid mixing them if we use a single engine!
    # Or just use OOSValidator logic to keep them isolated!
    # Let's run them isolated
    trades = []
    from app.diagnostics.telemetry import telemetry
    telemetry.reset()
    
    for symbol in symbols:
        asset_bars = [b for b in all_bars if b.symbol == symbol]
        asset_bars.sort(key=lambda x: x.timestamp)
        engine = create_engine_factory(use_adaptive=True, breakout_period=20)
        engine.run(asset_bars)
        trades.extend(engine.closed_trades)
    
    strategy_pnl = defaultdict(float)
    strategy_wins = defaultdict(int)
    strategy_losses = defaultdict(int)
    side_pnl = defaultdict(float)
    asset_pnl = defaultdict(float)
    
    wins = [t for t in trades if t.realized_pnl > 0]
    losses = [t for t in trades if t.realized_pnl <= 0]
    
    avg_win = sum(t.realized_pnl for t in wins) / len(wins) if wins else 0
    avg_loss = sum(abs(t.realized_pnl) for t in losses) / len(losses) if losses else 0
    
    for t in trades:
        # Strategies might be a dict or string, let's just use str()
        s = str(t.strategies) if hasattr(t, 'strategies') else "Unknown"
        strategy_pnl[s] += t.realized_pnl
        if t.realized_pnl > 0:
            strategy_wins[s] += 1
        else:
            strategy_losses[s] += 1
            
        side = str(t.direction)
        side_pnl[side] += t.realized_pnl
        asset_pnl[t.symbol] += t.realized_pnl

    print("STRATEGY PNL & W/L:")
    for s in strategy_pnl:
        w = strategy_wins[s]
        l = strategy_losses[s]
        wr = w/(w+l)*100 if w+l > 0 else 0
        print(f"  {s}: PNL ${strategy_pnl[s]:.2f}, W/L {w}/{l} ({wr:.1f}%)")
        
    print("\nLONG/SHORT PNL:")
    for s in side_pnl:
        print(f"  {s}: ${side_pnl[s]:.2f}")
        
    print("\nASSET PNL:")
    for a in asset_pnl:
        print(f"  {a}: ${asset_pnl[a]:.2f}")
        
    print(f"\nAVG WIN: ${avg_win:.2f}")
    print(f"AVG LOSS: -${avg_loss:.2f}")
    
    print(f"\nKRONOS VETOES: {telemetry.get_metric('kronos_vetoes', 0)}")
    print(f"DEATH MODE BLOCKS: {telemetry.get_metric('death_mode_blocks', 0)}")

if __name__ == "__main__":
    run()
