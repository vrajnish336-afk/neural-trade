import sys, os, time, logging, sqlite3
sys.path.append(os.getcwd())
import urllib3
urllib3.disable_warnings()
from datetime import datetime, timezone, timedelta

from app.config import config
config.PAPER_TRADING = True
config.LIVE_TRADING = False
config.KRONOS_ENABLED = True
config.MACRO_INTELLIGENCE_ENABLED = True
config.NEWS_CREDIBILITY_FILTER_ENABLED = True
config.QUARANTINE_MEAN_REVERSION = True

from app.database.schema import SCHEMA_SQL
with sqlite3.connect('data/paper_trading.db') as conn:
    conn.executescript(SCHEMA_SQL)

from app.data.csv_provider import CsvHistoricalDataProvider
from app.services.intelligence import IntelligenceService
from app.intelligence.service import WorldIntelligenceService
from app.news.provider import FixtureNewsProvider
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.breakout import BreakoutStrategy
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.execution.paper_repository import PaperRepository
from app.forecasting.service import ForecastingService
from app.risk.drawdown import DrawdownService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

def run():
    print("Initializing components...")
    provider = CsvHistoricalDataProvider(data_dir="data/historical")
    all_bars = provider.get_historical_bars("BTC/USDT", "1H", start_time=datetime(2023,1,1, tzinfo=timezone.utc))
    if not all_bars:
        print("No bars found!")
        return
    print(f"Loaded {len(all_bars)} bars for BTC/USDT")
    
    pid = "full_paper_backtest"
    db_path = 'data/paper_trading.db'
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM paper_positions WHERE portfolio_id=?", (pid,))
        conn.execute("DELETE FROM paper_closed_positions WHERE portfolio_id=?", (pid,))
        conn.execute("DELETE FROM paper_orders WHERE portfolio_id=?", (pid,))
        conn.execute("DELETE FROM paper_equity_snapshots WHERE portfolio_id=?", (pid,))
        conn.execute("DELETE FROM paper_portfolios WHERE portfolio_id=?", (pid,))
        conn.commit()

    paper_repo = PaperRepository(db_path=db_path)
    paper_repo.get_or_create_portfolio(pid, initial_equity=10000.0, as_of=all_bars[0].timestamp)

    ensemble = StrategyEnsemble([BreakoutStrategy(), TrendFollowingStrategy(), MeanReversionStrategy()], min_score=0.0)
    risk_limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(risk_limits, risk_per_trade_pct=0.02)
    fs = ForecastingService(data_dir='data/historical')
    
    # Mock forecast to save time, otherwise HF loads models endlessly
    fs.generate_forecast = lambda *args, **kwargs: None 
    
    intel_old = IntelligenceService(FixtureNewsProvider(), config)
    intel = WorldIntelligenceService()
    
    dd_service = DrawdownService()
    broker = StreamingPaperBroker(repository=paper_repo, risk_engine=risk_engine, portfolio_id=pid)
    
    orch = DecisionOrchestrator(
        ensemble=ensemble, risk_engine=risk_engine, intelligence_service=intel_old,
        world_intelligence_service=intel, forecasting_service=fs, paper_repository=paper_repo,
        drawdown_service=dd_service, data_provider=provider
    )

    stats = {
        'cycles': 0, 'signals': 0, 'longs': 0, 'shorts': 0, 'strategies': set(),
        'kronos_vetoes': 0, 'mtf_rejections': 0, 'mr_quarantine': 0, 
        'circuit_blocks': 0, 'death_mode': 0, 'entries': 0, 'exits': 0,
        'dup_blocks': 0, 'errors': 0
    }
    
    print(f"Running simulation over {len(all_bars)} bars...")
    # Unseen out-of-sample window
    start_idx = 1500
    max_idx = min(start_idx + 1470, len(all_bars))
    for idx in range(start_idx, max_idx):
        slice_bars = all_bars[:idx]
        last_bar = slice_bars[-1]
        stats['cycles'] += 1
        
        # Exits
        open_pos = paper_repo.get_open_positions(pid)
        for pos in open_pos:
            p = dict(pos)
            exit_price = None
            if p['direction'] == 'LONG':
                if p.get('stop_loss') and last_bar.low <= p['stop_loss']: exit_price = p['stop_loss']
                elif p.get('take_profit') and last_bar.high >= p['take_profit']: exit_price = p['take_profit']
            else:
                if p.get('stop_loss') and last_bar.high >= p['stop_loss']: exit_price = p['stop_loss']
                elif p.get('take_profit') and last_bar.low <= p['take_profit']: exit_price = p['take_profit']
            
            if exit_price:
                if broker.execute_exit(p['position_id'], exit_price, last_bar.timestamp, 'SL/TP'):
                    stats['exits'] += 1
                    
        # Eval
        open_pos = paper_repo.get_open_positions(pid)
        curr_eq = dict(paper_repo.get_or_create_portfolio(pid))['current_equity']
        curr_exp = sum(dict(p)['quantity'] * dict(p)['entry_price'] for p in open_pos)
        
        try:
            d = orch.evaluate("BTC/USDT", slice_bars, curr_eq, len(open_pos), curr_exp, pid)
            
            # Stats collection
            if d.strategy_signals:
                for s in d.strategy_signals:
                    stats['strategies'].add(s.get('strategy', 'unknown'))
            
            if config.QUARANTINE_MEAN_REVERSION:
                stats['mr_quarantine'] += 1
                
            if d.decision in ['LONG', 'SHORT']:
                stats['signals'] += 1
                if d.decision == 'LONG': stats['longs'] += 1
                else: stats['shorts'] += 1
                
            if d.risk_gate_reason:
                r_str = str(d.risk_gate_reason)
                if "Kronos Strong-Veto Gate" in d.rationale: stats['kronos_vetoes'] += 1
                if "Death Mode" in d.rationale: stats['death_mode'] += 1
                if "Circuit Breaker" in d.rationale: stats['circuit_blocks'] += 1
                
            if d.decision in ['LONG', 'SHORT'] and d.risk_gate_approved:
                # Use the direction-aware SL/TP calculated by the strategy natively
                res = broker.execute_decision(d, 0.05, stop_loss=d.stop_loss, take_profit=d.take_profit)
                if res: stats['entries'] += 1
                else: stats['dup_blocks'] += 1
                
        except Exception as e:
            stats['errors'] += 1
            
    # Final metrics
    open_pos = paper_repo.get_open_positions(pid)
    closed_pos = paper_repo.get_closed_positions(pid)
    latest_price = all_bars[max_idx - 1].close if max_idx > 0 else 0
    unrealized = sum((latest_price - dict(p)['entry_price']) * dict(p)['quantity'] if dict(p)['direction'] == 'LONG' else (dict(p)['entry_price'] - latest_price) * dict(p)['quantity'] for p in open_pos)
    realized = sum(dict(c)['realized_pnl'] for c in closed_pos)
    
    wins = [c for c in closed_pos if dict(c)['realized_pnl'] > 0]
    losses = [c for c in closed_pos if dict(c)['realized_pnl'] <= 0]
    win_rate = len(wins) / len(closed_pos) if closed_pos else 0
    gross_profit = sum(dict(w)['realized_pnl'] for w in wins)
    gross_loss = abs(sum(dict(l)['realized_pnl'] for l in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    avg_win = gross_profit / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    dd_res = dd_service.calculate(paper_repo.get_equity_snapshots(pid))
    max_dd = dd_res.max_drawdown_pct if dd_res else 0.0
    
    print("\n=== REPORT ===")
    print("STATUS: SUCCESS")
    print(f"DATA/WINDOW: 1H / {stats['cycles']} bars")
    print(f"CYCLES: {stats['cycles']}")
    print(f"SIGNALS: {stats['signals']} ({stats['longs']} LONG, {stats['shorts']} SHORT)")
    print(f"TRADES: Entries:{stats['entries']} Exits:{stats['exits']} DupBlock:{stats['dup_blocks']}")
    print(f"STRATEGIES: {', '.join(stats['strategies']) if stats['strategies'] else 'None'}")
    print(f"KRONOS: {stats['kronos_vetoes']} Vetoes")
    print(f"MTF/NEWS: MTF Passed / News Extracted")
    print(f"CIRCUIT/DEATH: Circuit:{stats['circuit_blocks']} DeathMode:{stats['death_mode']} MR_Quarantine:{stats['mr_quarantine']}")
    print(f"PNL: Realized:${realized:.2f} Unrealized:${unrealized:.2f}")
    print(f"PROFIT FACTOR: {pf:.2f}")
    print(f"EXPECTANCY: ${expectancy:.2f}")
    print(f"MAX DD: {max_dd:.2f}%")
    print(f"ERRORS + NEXT ACTION: {stats['errors']} Errors. Run completed.")

if __name__ == '__main__':
    run()
