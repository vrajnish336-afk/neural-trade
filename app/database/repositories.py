import sqlite3
import uuid
import logging
from typing import Optional, Any
from app.config import config
from app.backtesting.models import BacktestResult

logger = logging.getLogger(__name__)

class BacktestRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def save(self, result: BacktestResult) -> Optional[str]:
        if not config.ENABLE_PERSISTENCE:
            return None
            
        run_id = str(uuid.uuid4())
        
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                
                # Save Backtest Summary
                cursor.execute(
                    '''INSERT INTO backtests (id, timestamp, initial_capital, final_equity, total_return_pct, number_of_trades, winning_trades, losing_trades) 
                       VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?)''',
                    (run_id, result.initial_capital, result.final_equity, result.total_return_pct, 
                     result.number_of_trades, result.winning_trades, result.losing_trades)
                )
                
                # Save Trades
                for trade in result.trades:
                    cursor.execute(
                        '''INSERT INTO trades (id, backtest_id, symbol, direction, entry_time, exit_time, entry_price, exit_price, quantity, realized_pnl, exit_reason, regime, score, strategies, risk_reason, sentiment_label, anomaly_flags, fakeout_risk) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (str(uuid.uuid4()), run_id, trade.symbol, trade.direction, 
                         trade.entry_time.isoformat() if trade.entry_time else None, 
                         trade.exit_time.isoformat() if trade.exit_time else None, 
                         trade.entry_price, trade.exit_price, trade.quantity, trade.realized_pnl, 
                         trade.exit_reason, trade.regime, trade.score, trade.strategies, trade.risk_reason,
                         trade.sentiment_label, trade.anomaly_flags, trade.fakeout_risk)
                    )
                    
                # Save Equity Curve (Just save the final point or a series if available)
                # Currently we only track final_equity. Wait, do we track equity curve in backtest engine?
                # We will update BacktestResult to have an equity_curve if possible.
                
                conn.commit()
            return run_id
        except Exception as e:
            logger.error("Persistence failure: %s", e)
            return None

class AnalyticsRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def save_report(self, report: Any) -> Optional[str]:
        if not config.ENABLE_PERSISTENCE:
            return None
            
        run_id = str(uuid.uuid4())
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO analytics_runs (id, backtest_id, timestamp, report_json) 
                       VALUES (?, ?, datetime('now'), ?)''',
                    (run_id, report.backtest_id, report.model_dump_json())
                )
                conn.commit()
            return run_id
        except Exception as e:
            logger.error("Analytics persistence failure: %s", e)
            return None

class ResearchRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def save_experiment(self, experiment: Any) -> Optional[str]:
        if not config.ENABLE_PERSISTENCE:
            return None
            
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO research_experiments (id, timestamp, experiment_json) 
                       VALUES (?, datetime('now'), ?)''',
                    (experiment.experiment_id, experiment.model_dump_json())
                )
                conn.commit()
            return experiment.experiment_id
        except Exception as e:
            logger.error("Research persistence failure: %s", e)
            return None
