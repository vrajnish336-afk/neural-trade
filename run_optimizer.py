import logging
import statistics
from typing import List
from datetime import datetime, timezone
import warnings

from app.config import config
from app.database.schema import init_db
from app.research.dataset import generate_synthetic_data
from app.research.robustness.runner import create_engine_factory
from app.research.robustness.walk_forward import run_walk_forward_robustness
from app.backtesting.models import CostConfig

warnings.filterwarnings('ignore')
logging.getLogger("app.backtesting.engine").setLevel(logging.WARNING)

def evaluate_param(min_score: float, bars: list) -> dict:
    config.MIN_SIGNAL_SCORE = min_score
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False
    config.QUARANTINE_MEAN_REVERSION = True
    
    def engine_factory():
        eng = create_engine_factory(use_adaptive=True, breakout_period=20)
        eng.cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.001)
        return eng
        
    wf_results = run_walk_forward_robustness(
        bars=bars,
        engine_factory=engine_factory,
        window_size=2000,
        step_size=2000
    )
    
    folds_data = []
    pfs = []
    dds = []
    returns = []
    expectancies = []
    
    total_net_pnl = 0.0
    total_trades = 0
    total_gross_profit = 0.0
    total_gross_loss = 0.0
    
    for r in wf_results:
        pfs.append(r.profit_factor)
        dds.append(r.max_drawdown_pct)
        returns.append(r.return_pct)
        
        total_gross_profit += r.gross_profit
        total_gross_loss += r.gross_loss
        
        wins = int(round(r.trades * r.win_rate))
        losses = r.trades - wins
        
        exp = ((r.return_pct / 100.0) * 10000.0) / r.trades if r.trades > 0 else 0.0
        expectancies.append(exp)
        
        total_net_pnl += (r.return_pct / 100.0) * 10000.0
        total_trades += r.trades
        
        folds_data.append({
            "id": r.window_id,
            "trades": r.trades,
            "wins": wins,
            "losses": losses,
            "pf": r.profit_factor,
            "ret": r.return_pct,
            "dd": r.max_drawdown_pct,
            "expectancy": exp
        })
        
    if total_gross_loss == 0.0:
        agg_pf = float('inf') if total_gross_profit > 0 else 0.0
    else:
        agg_pf = total_gross_profit / total_gross_loss
    
    avg_dd = sum(dds) / len(dds) if dds else 0.0
    
    min_pf = min(pfs) if pfs else 0.0
    min_exp = min(expectancies) if expectancies else 0.0
    median_exp = statistics.median(expectancies) if expectancies else 0.0
    
    expectancy = total_net_pnl / total_trades if total_trades > 0 else 0.0
    
    # Check for severely negative fold (e.g. PF < 0.5 or high loss)
    has_severe_loss = any(f["pf"] < 0.5 and f["trades"] > 0 for f in folds_data)
    min_fold_trades = min(f["trades"] for f in folds_data) if folds_data else 0
    
    return {
        "min_score": min_score,
        "avg_pf": agg_pf,
        "avg_dd": avg_dd,
        "expectancy": expectancy,
        "min_pf": min_pf,
        "min_exp": min_exp,
        "median_exp": median_exp,
        "total_trades": total_trades,
        "min_fold_trades": min_fold_trades,
        "has_severe_loss": has_severe_loss,
        "folds": len(wf_results),
        "folds_data": folds_data
    }

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
    
    baseline = evaluate_param(50.0, all_bars)
    
    candidates = [60.0, 70.0, 75.0, 80.0, 85.0]
    results = []
    for c in candidates:
        results.append(evaluate_param(c, all_bars))
        
    # Validity criteria
    valid = []
    for r in results:
        # minimum total closed trades >= 30
        # positive aggregate expectancy
        # max DD < 30%
        # no severely losing validation fold
        # walk-forward fold evidence required
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
        # rank by expectancy instead of average PF alone
        best = max(valid, key=lambda x: (x["expectancy"], x["avg_pf"]))
        
    print("STATUS: COMPLETED")
    
    max_trades = max(r["total_trades"] for r in results)
    if max_trades < 30:
        print("STATUS: INSUFFICIENT DATA")
        
    print(f"FOLDS: {baseline['folds']}")
    print(f"PARAMETERS TESTED: MIN_SIGNAL_SCORE [{', '.join(map(str, candidates))}]")
    print(f"VALID CANDIDATES: {len(valid)}")
    print(f"REJECTED CANDIDATES: {len(results) - len(valid)}")
    
    if best:
        print(f"BEST VALID PROPOSAL: MIN_SIGNAL_SCORE = {best['min_score']}")
        print(f"PROPOSAL PF/EXP/DD: {best['avg_pf']:.2f} / ${best['expectancy']:.2f} / {best['avg_dd']:.2f}%")
        print(f"TRADE COUNT: {best['total_trades']} (Min fold trades: {best['min_fold_trades']})")
        print(f"MIN FOLD PF/EXP: {best['min_pf']:.2f} / ${best['min_exp']:.2f}")
        print(f"MEDIAN FOLD EXP: ${best['median_exp']:.2f}")
        
        consistency = "High" if not best["has_severe_loss"] and best["min_pf"] > 0.8 else "Low/Medium"
        print(f"FOLD CONSISTENCY: {consistency}")
        
        # Report folds
        for f in best["folds_data"]:
            print(f"  Fold {f['id']}: Trades={f['trades']} (W={f['wins']} L={f['losses']}), PF={f['pf']:.2f}, Exp=${f['expectancy']:.2f}")
    else:
        print("BEST VALID PROPOSAL: NO VALID PROPOSAL")
        print("PROPOSAL PF/EXP/DD: N/A")
        print("TRADE COUNT: N/A")
        print("MIN FOLD PF/EXP: N/A")
        print("MEDIAN FOLD EXP: N/A")
        print("FOLD CONSISTENCY: N/A")
        
    print("FINAL OOS TOUCHED: NO")
    print("AUTO-APPLIED: NO")
    print("NEXT ACTION: Await review of proposal")

if __name__ == "__main__":
    run()
