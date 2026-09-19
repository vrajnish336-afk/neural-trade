import sqlite3
import uuid
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
import hashlib

from app.config import config

logger = logging.getLogger(__name__)

class PaperRepositoryException(Exception):
    pass

class PaperRepository:
    """
    Manages persistent state for the paper portfolio, including positions and orders.
    Enforces atomic transactions and idempotency.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_or_create_portfolio(self, portfolio_id: str, initial_equity: float = 10000.0) -> sqlite3.Row:
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM paper_portfolios WHERE portfolio_id = ?", (portfolio_id,))
                row = cursor.fetchone()
                if row:
                    return row
                    
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    """
                    INSERT INTO paper_portfolios (portfolio_id, initial_equity, current_equity, current_cash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (portfolio_id, initial_equity, initial_equity, initial_equity, now, now)
                )
                
                snapshot_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO paper_equity_snapshots (snapshot_id, portfolio_id, timestamp, current_equity, current_cash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (snapshot_id, portfolio_id, now, initial_equity, initial_equity, now)
                )
                
                cursor.execute("SELECT * FROM paper_portfolios WHERE portfolio_id = ?", (portfolio_id,))
                return cursor.fetchone()

    def get_open_positions(self, portfolio_id: str) -> List[sqlite3.Row]:
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM paper_positions WHERE portfolio_id = ?", (portfolio_id,))
                return cursor.fetchall()
                
    def get_recent_orders(self, portfolio_id: str, limit: int = 5) -> List[sqlite3.Row]:
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM paper_orders WHERE portfolio_id = ? ORDER BY created_at DESC LIMIT ?", 
                    (portfolio_id, limit)
                )
                return cursor.fetchall()
            
    def generate_decision_id(self, symbol: str, timestamp: datetime) -> str:
        """
        Creates a deterministic decision identity to prevent duplicate orders.
        """
        raw = f"{symbol}_{timestamp.isoformat()}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    def execute_order(
        self,
        portfolio_id: str,
        decision_id: str,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        actual_price: float,
        commission: float,
        slippage: float,
        timestamp: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy: Optional[str] = None,
        unrealized_pnl: float = 0.0,
        regime: Optional[str] = None
    ) -> bool:
        """
        Atomically executes an entry order, creating a position and updating cash/equity.
        Returns True if executed, False if duplicate decision.
        """
        now = datetime.now(timezone.utc).isoformat()
        order_id = str(uuid.uuid4())
        position_id = str(uuid.uuid4())
        ts_str = timestamp.isoformat()
        regime_val = regime if regime else "UNKNOWN"
        
        # Calculate cash impact (commission + margin/value).
        # We assume the position reduces cash by the entire value + commission for simplicity of paper accounting,
        # or we track equity dynamically. Here, cash is reduced by commission.
        # Actually, let's look at backtesting engine: 
        # `self.equity -= comm` (equity is essentially cash + realized PnL before unrealized).
        
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                
                try:
                    # Check Idempotency
                    cursor.execute("SELECT order_id FROM paper_orders WHERE decision_id = ?", (decision_id,))
                    if cursor.fetchone():
                        logger.warning(f"Idempotency block: Decision {decision_id} already executed.")
                        return False
                        
                    # 1. Insert Order
                    cursor.execute(
                        """
                        INSERT INTO paper_orders (
                            order_id, portfolio_id, decision_id, symbol, direction, 
                            quantity, price, timestamp, status, commission, slippage, created_at, reason, regime, strategy
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (order_id, portfolio_id, decision_id, symbol, direction, quantity, 
                         price, ts_str, "FILLED", commission, slippage, now, None, regime_val, strategy)
                    )
                    
                    # 2. Insert Position
                    cursor.execute(
                        """
                        INSERT INTO paper_positions (
                            position_id, portfolio_id, symbol, direction, entry_time, 
                            entry_price, quantity, stop_loss, take_profit, strategy, created_at, updated_at, regime
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (position_id, portfolio_id, symbol, direction, ts_str,
                         actual_price, quantity, stop_loss, take_profit, strategy, now, now, regime_val)
                    )
                    
                    # 3. Update Portfolio Cash/Equity
                    cursor.execute(
                        """
                        UPDATE paper_portfolios
                        SET current_equity = current_equity - ?,
                            current_cash = current_cash - ?,
                            updated_at = ?
                        WHERE portfolio_id = ?
                        """,
                        (commission, commission, now, portfolio_id)
                    )
                    
                    # 4. Save Snapshot
                    cursor.execute("SELECT current_equity, current_cash FROM paper_portfolios WHERE portfolio_id = ?", (portfolio_id,))
                    port = cursor.fetchone()
                    
                    snapshot_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO paper_equity_snapshots (snapshot_id, portfolio_id, timestamp, current_equity, current_cash, created_at, unrealized_pnl)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (snapshot_id, portfolio_id, ts_str, port['current_equity'], port['current_cash'], now, unrealized_pnl)
                    )
                    
                    return True
                    
                except sqlite3.IntegrityError as e:
                    logger.error(f"Integrity Error executing order: {e}")
                    return False
                except Exception as e:
                    logger.error(f"Error executing order: {e}")
                    raise PaperRepositoryException(f"Failed to execute order: {e}")

    def record_rejected_trade(self, portfolio_id: str, decision_id: str, symbol: str, direction: str, 
                              reason: str, timestamp: datetime, strategy: Optional[str] = None, regime: Optional[str] = None):
        """
        Record a rejected or vetoed trade into paper_orders for analytics.
        """
        now = datetime.now(timezone.utc).isoformat()
        ts_str = timestamp.isoformat()
        order_id = str(uuid.uuid4())
        
        regime_val = regime if regime else "UNKNOWN"
        
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO paper_orders (
                            order_id, portfolio_id, decision_id, symbol, direction, 
                            quantity, price, timestamp, status, commission, slippage, created_at, reason, regime, strategy
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (order_id, portfolio_id, decision_id, symbol, direction, 0.0, 
                         0.0, ts_str, "REJECTED", 0.0, 0.0, now, reason, regime_val, strategy)
                    )
                except sqlite3.IntegrityError as e:
                    logger.warning(f"Failed to record rejected trade {decision_id}: {e}")
                    pass # Already recorded
                    
    def execute_exit(
        self,
        portfolio_id: str,
        position_id: str,
        exit_price: float,
        actual_price: float,
        commission: float,
        slippage: float,
        timestamp: datetime,
        unrealized_pnl: float = 0.0,
        regime: Optional[str] = None
    ) -> bool:
        """
        Atomically executes an exit order, removing the position and realizing PnL.
        """
        now = datetime.now(timezone.utc).isoformat()
        ts_str = timestamp.isoformat()
        order_id = str(uuid.uuid4())
        
        regime_val = regime if regime else "UNKNOWN"
        
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                
                try:
                    # Verify position exists
                    cursor.execute("SELECT * FROM paper_positions WHERE position_id = ? AND portfolio_id = ?", (position_id, portfolio_id))
                    pos = cursor.fetchone()
                    if not pos:
                        logger.error(f"Cannot exit position {position_id} - not found.")
                        return False
                        
                    direction = pos['direction']
                    quantity = pos['quantity']
                    entry_price = pos['entry_price']
                    symbol = pos['symbol']
                    
                    # Handle backwards compatibility if the row doesn't have the column yet
                    strategy_val = pos['strategy'] if 'strategy' in pos.keys() else None
                    
                    # Verify price is valid
                    if exit_price <= 0:
                        logger.error(f"Cannot exit position {position_id} - invalid exit price {exit_price}")
                        return False
                    
                    # Check Idempotency for exit order
                    decision_id = f"EXIT_{position_id}_{ts_str}"
                    cursor.execute("SELECT order_id FROM paper_orders WHERE decision_id = ?", (decision_id,))
                    if cursor.fetchone():
                        logger.warning(f"Idempotency block: Exit decision {decision_id} already executed.")
                        return False
                    
                    # Calculate PnL
                    if direction == "LONG":
                        pnl = (actual_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - actual_price) * quantity
                        
                    equity_change = pnl - commission
                    
                    # 1. Insert Exit Order
                    cursor.execute(
                        """
                        INSERT INTO paper_orders (
                            order_id, portfolio_id, decision_id, symbol, direction, 
                            quantity, price, timestamp, status, commission, slippage, created_at, reason, regime, strategy
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (order_id, portfolio_id, decision_id, symbol, f"CLOSE_{direction}", quantity, 
                         exit_price, ts_str, "FILLED", commission, slippage, now, None, regime_val, strategy_val)
                    )
                    
                    # 2. Insert into Closed Positions Ledger
                    cursor.execute(
                        """
                        INSERT INTO paper_closed_positions (
                            position_id, portfolio_id, symbol, direction, entry_time, entry_price, 
                            exit_time, exit_price, quantity, realized_pnl, exit_reason, strategy, regime, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (position_id, portfolio_id, symbol, direction, pos['entry_time'], entry_price,
                         ts_str, actual_price, quantity, pnl, "MANUAL_EXIT", strategy_val, regime_val, now)
                    )
                    
                    # 3. Delete Position from open inventory
                    cursor.execute("DELETE FROM paper_positions WHERE position_id = ?", (position_id,))
                    
                    # 4. Update Portfolio Cash/Equity
                    cursor.execute(
                        """
                        UPDATE paper_portfolios
                        SET current_equity = current_equity + ?,
                            current_cash = current_cash + ?,
                            updated_at = ?
                        WHERE portfolio_id = ?
                        """,
                        (equity_change, equity_change, now, portfolio_id)
                    )
                    
                    # 5. Save Snapshot
                    cursor.execute("SELECT current_equity, current_cash FROM paper_portfolios WHERE portfolio_id = ?", (portfolio_id,))
                    port = cursor.fetchone()
                    
                    snapshot_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO paper_equity_snapshots (snapshot_id, portfolio_id, timestamp, current_equity, current_cash, created_at, unrealized_pnl)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (snapshot_id, portfolio_id, ts_str, port['current_equity'], port['current_cash'], now, unrealized_pnl)
                    )
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"Error executing exit: {e}")
                    raise PaperRepositoryException(f"Failed to execute exit: {e}")
                    
    def get_closed_positions(self, portfolio_id: str, limit: int = 20) -> List[sqlite3.Row]:
        """
        Retrieves the read-only ledger of closed positions for a portfolio, sorted by newest exit first.
        """
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM paper_closed_positions WHERE portfolio_id = ? ORDER BY exit_time DESC LIMIT ?", 
                    (portfolio_id, limit)
                )
                return cursor.fetchall()
                
    def get_equity_snapshots(self, portfolio_id: str, as_of: Optional[datetime] = None) -> List[sqlite3.Row]:
        """
        Retrieves historical equity snapshots ordered by chronological timestamp.
        If as_of is provided, excludes snapshots strictly after that timestamp.
        """
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                if as_of:
                    as_of_str = as_of.isoformat()
                    cursor.execute(
                        "SELECT * FROM paper_equity_snapshots WHERE portfolio_id = ? AND timestamp <= ? ORDER BY timestamp ASC",
                        (portfolio_id, as_of_str)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM paper_equity_snapshots WHERE portfolio_id = ? ORDER BY timestamp ASC",
                        (portfolio_id,)
                    )
                return cursor.fetchall()
