import os, sys, logging, sqlite3
sys.path.append(str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from datetime import datetime, timezone
import pandas as pd

from app.config import config
from app.data.csv_provider import CsvHistoricalDataProvider
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.forecasting.service import ForecastingService
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.breakout import BreakoutStrategy
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.drawdown import DrawdownService
from app.execution.paper_repository import PaperRepository
from app.execution.streaming_paper_broker import StreamingPaperBroker

from app.database.schema import SCHEMA_SQL

logging.basicConfig(level=logging.ERROR)

db_file = 'data/final_oos_validation.sqlite'
with sqlite3.connect(db_file) as conn:
    conn.executescript(SCHEMA_SQL)
    conn.commit()

provider = CsvHistoricalDataProvider('data/historical')

datasets = [
    ('BTC/USDT', '1H', 'BTC_USDT_1H'),
    ('BTC/USDT', '4H', 'BTC_USDT_4H'),
    ('ETH/USDT', '1H', 'ETH_USDT_1H'),
    ('ETH/USDT', '4H', 'ETH_USDT_4H'),
    ('SOL/USDT', '1H', 'SOL_USDT_1H'),
    ('SOL/USDT', '4H', 'SOL_USDT_4H'),
    ('BNB/USDT', '1H', 'BNB_USDT_1H'),
    ('BNB/USDT', '4H', 'BNB_USDT_4H')
]

overall_results = {}

for symbol, timeframe, prefix in datasets:
    all_bars = provider.get_historical_bars(symbol, timeframe, start_time=datetime(1970, 1, 1, tzinfo=timezone.utc))
    start_idx = 1000
    end_idx = min(2900, len(all_bars))
    
    for veto_mode in [False, True]:
        pid = f"paper_val_{prefix.lower()}_{'on' if veto_mode else 'off'}"
        config.KRONOS_STRONG_VETO_ENABLED = veto_mode
        config.PAPER_TRADING = True
        config.LIVE_TRADING = False
        
        with sqlite3.connect(db_file) as conn:
            conn.execute("DELETE FROM paper_positions WHERE portfolio_id=?", (pid,))
            conn.execute("DELETE FROM paper_closed_positions WHERE portfolio_id=?", (pid,))
            conn.execute("DELETE FROM paper_orders WHERE portfolio_id=?", (pid,))
            conn.execute("DELETE FROM paper_equity_snapshots WHERE portfolio_id=?", (pid,))
            conn.execute("DELETE FROM paper_portfolios WHERE portfolio_id=?", (pid,))
            conn.commit()
            
        paper_repo = PaperRepository(db_path=db_file)
        paper_repo.get_or_create_portfolio(pid, initial_equity=10000.0)
        
        ensemble = StrategyEnsemble([BreakoutStrategy(), TrendFollowingStrategy(), MeanReversionStrategy()], min_score=0.0)
        risk_limits = PortfolioRiskLimits(initial_equity=10000.0)
        risk_engine = RiskEngine(risk_limits, risk_per_trade_pct=0.02)
        fs = ForecastingService(data_dir='data/historical')
        forecast_cache = {}
        real_gen_forecast = fs.generate_forecast
        def cached_generate_forecast(sym, tf, w_size, hor, model_choice="kronos", evaluation_boundary=None):
            latest_t = slice_bars[-1].timestamp if 'slice_bars' in locals() and slice_bars else None
            key = (sym, tf, latest_t)
            if key in forecast_cache:
                return forecast_cache[key]
            res = real_gen_forecast(sym, tf, w_size, hor, model_choice=model_choice, evaluation_boundary=latest_t)
            forecast_cache[key] = res
            return res
        fs.generate_forecast = cached_generate_forecast
        dd_service = DrawdownService()
        
        broker = StreamingPaperBroker(repository=paper_repo, risk_engine=risk_engine, portfolio_id=pid)
        orch = DecisionOrchestrator(
            ensemble=ensemble, risk_engine=risk_engine, intelligence_service=None,
            forecasting_service=fs, paper_repository=paper_repo, drawdown_service=dd_service,
            data_provider=provider
        )
        
        executed_entries = 0
        executed_exits = 0
        down_vetoes = 0
        unknown_vetoes = 0
        dup_blocked = 0
        errors_count = 0
        
        for idx in range(start_idx, end_idx):
            slice_bars = all_bars[:idx]
            latest_bar = slice_bars[-1]
            
            open_pos = paper_repo.get_open_positions(pid)
            
            # Exits
            for pos in open_pos:
                p_dict = dict(pos)
                pos_id = p_dict['position_id']
                direction = p_dict['direction']
                stop_loss = p_dict.get('stop_loss')
                take_profit = p_dict.get('take_profit')
                
                hit_exit = False
                exit_price = latest_bar.close
                reason = 'STOP_LOSS'
                
                if direction == 'LONG':
                    if stop_loss and latest_bar.low <= stop_loss:
                        hit_exit = True
                        exit_price = stop_loss
                    elif take_profit and latest_bar.high >= take_profit:
                        hit_exit = True
                        exit_price = take_profit
                        reason = 'TAKE_PROFIT'
                elif direction == 'SHORT':
                    if stop_loss and latest_bar.high >= stop_loss:
                        hit_exit = True
                        exit_price = stop_loss
                    elif take_profit and latest_bar.low <= take_profit:
                        hit_exit = True
                        exit_price = take_profit
                        reason = 'TAKE_PROFIT'
                        
                if hit_exit:
                    res = broker.execute_exit(pos_id, exit_price=exit_price, timestamp=latest_bar.timestamp, reason=reason)
                    if res:
                        executed_exits += 1
                        
            # Decision & Execution
            open_pos = paper_repo.get_open_positions(pid)
            curr_portfolio = dict(paper_repo.get_or_create_portfolio(pid))
            curr_equity = curr_portfolio['current_equity']
            curr_exposure = sum(dict(p)['quantity'] * dict(p)['entry_price'] for p in open_pos)
            
            try:
                d = orch.evaluate(
                    symbol=symbol, bars=slice_bars, current_equity=curr_equity,
                    current_positions_count=len(open_pos), current_exposure=curr_exposure, portfolio_id=pid
                )
                
                if veto_mode and d.risk_gate_reason and "Kronos Strong-Veto Gate" in d.rationale:
                    r_str = str(d.risk_gate_reason)
                    if "predicts DOWN" in r_str:
                        down_vetoes += 1
                    else:
                        unknown_vetoes += 1
                        
                if d.risk_gate_approved and d.paper_execution_eligible and d.decision in ['LONG', 'SHORT']:
                    res = broker.execute_decision(
                        d, position_size=0.01,
                        stop_loss=latest_bar.close * 0.93 if d.decision == 'LONG' else latest_bar.close * 1.07,
                        take_profit=latest_bar.close * 1.15 if d.decision == 'LONG' else latest_bar.close * 0.85
                    )
                    if res:
                        executed_entries += 1
                    else:
                        dup_blocked += 1
            except Exception as e:
                errors_count += 1

        final_open = paper_repo.get_open_positions(pid)
        final_closed = paper_repo.get_closed_positions(pid, limit=1000)
        
        latest_price = all_bars[end_idx - 1].close
        unrealized_pnl = sum((latest_price - dict(p)['entry_price']) * dict(p)['quantity'] if dict(p)['direction'] == 'LONG' else (dict(p)['entry_price'] - latest_price) * dict(p)['quantity'] for p in final_open)
        realized_pnl = sum(dict(c)['realized_pnl'] for c in final_closed) if final_closed else 0.0
        
        wins = sum(1 for c in final_closed if dict(c)['realized_pnl'] > 0)
        losses = sum(1 for c in final_closed if dict(c)['realized_pnl'] < 0)
        
        snapshots = paper_repo.get_equity_snapshots(pid)
        dd_res = dd_service.calculate(snapshots)
        max_dd_pct = dd_res.max_drawdown_pct if dd_res else 0.0

        from app.diagnostics.participation import calculate_participation_metrics, format_counterfactual_disclaimer

        part_metrics = calculate_participation_metrics(
            executed_entries=executed_entries,
            down_vetoes=down_vetoes,
            unknown_vetoes=unknown_vetoes,
            dup_blocked=dup_blocked,
            closed_trades=len(final_closed),
            open_positions=len(final_open),
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            max_dd_pct=max_dd_pct
        )
        
        key = f"{prefix}_{'VETO_ON' if veto_mode else 'VETO_OFF'}"
        overall_results[key] = {
            'eligible_signals': part_metrics['eligible_signals'],
            'executed_entries': executed_entries,
            'closed_trades': len(final_closed),
            'open_positions': len(final_open),
            'wins': wins,
            'losses': losses,
            'realized_pnl': part_metrics['realized_pnl'],
            'unrealized_pnl': part_metrics['unrealized_pnl'],
            'max_dd_pct': part_metrics['max_dd_pct'],
            'down_vetoes': down_vetoes,
            'unknown_vetoes': unknown_vetoes,
            'dup_blocked': dup_blocked,
            'participation_rate_pct': part_metrics['participation_rate_pct'],
            'zero_exposure': part_metrics['zero_exposure'],
            'status_flag': part_metrics['status_flag'],
            'warning': part_metrics['warning'],
            'errors': errors_count
        }

print("\n=== MULTI-ASSET PAPER VALIDATION RESULTS ===")
for k, v in overall_results.items():
    print(f"{k}: {v}")
print("\n" + format_counterfactual_disclaimer())
