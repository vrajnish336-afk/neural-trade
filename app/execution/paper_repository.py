import sqlite3
import uuid
import logging
from typing import Optional, List, Dict, Any
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

    def get_or_create_portfolio(self, portfolio_id: str, initial_equity: float = 10000.0, as_of: Optional[datetime] = None) -> sqlite3.Row:
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM paper_portfolios WHERE portfolio_id = ?", (portfolio_id,))
                row = cursor.fetchone()
                if row:
                    return row
                    
                now = as_of.isoformat() if as_of else datetime.now(timezone.utc).isoformat()
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

    def calculate_unrealized_pnl(self, portfolio_id: str, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculates the combined unrealized PnL of all currently open positions for the portfolio.
        Uses current_prices[symbol] if provided, else defaults to pos['entry_price'] (0 PnL).
        """
        positions = self.get_open_positions(portfolio_id)
        if not positions:
            return 0.0
            
        prices = current_prices or {}
        total_unrealized = 0.0
        for pos in positions:
            sym = pos['symbol']
            curr_price = prices.get(sym)
            if curr_price is not None and curr_price > 0:
                direction = pos['direction']
                qty = float(pos['quantity'])
                entry = float(pos['entry_price'])
                if direction == 'LONG':
                    total_unrealized += (curr_price - entry) * qty
                elif direction == 'SHORT':
                    total_unrealized += (entry - curr_price) * qty
        return total_unrealized

    def get_dynamic_equity(self, portfolio_id: str, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculates true dynamic equity: Realized Cash + Combined unrealized PnL of all open positions.
        """
        portfolio = self.get_or_create_portfolio(portfolio_id)
        current_cash = float(portfolio['current_cash'])
        unrealized = self.calculate_unrealized_pnl(portfolio_id, current_prices)
        return current_cash + unrealized

    def sync_dynamic_equity(self, portfolio_id: str, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        Updates paper_portfolios.current_equity with the true dynamic equity
        (Realized Cash + Combined unrealized PnL) and returns it.
        """
        dynamic_equity = self.get_dynamic_equity(portfolio_id, current_prices)
        now = datetime.now(timezone.utc).isoformat()
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                conn.execute(
                    "UPDATE paper_portfolios SET current_equity = ?, updated_at = ? WHERE portfolio_id = ?",
                    (dynamic_equity, now, portfolio_id)
                )
        return dynamic_equity
                
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
            
    def generate_decision_id(
        self, 
        symbol: str, 
        timestamp: datetime, 
        decision: Optional[str] = None, 
        strategy_name: Optional[str] = None
    ) -> str:
        """
        Creates a deterministic decision identity to prevent duplicate orders.
        Includes decision (direction/action) and strategy_name in the hash payload
        alongside symbol and timestamp to prevent cross-action/strategy collisions.
        """
        decision_str = str(decision or "").strip()
        strategy_str = str(strategy_name or "").strip()
        raw = f"{symbol}_{timestamp.isoformat()}_{decision_str}_{strategy_str}".encode('utf-8')
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

    def record_rejected_trade(
        self, 
        portfolio_id: str, 
        decision_id: str, 
        symbol: str, 
        decision: Optional[str] = None, 
        reason: str = "", 
        timestamp: Optional[datetime] = None, 
        strategy: Optional[str] = None, 
        regime: Optional[str] = None,
        direction: Optional[str] = None
    ) -> None:
        """
        Record a rejected or vetoed trade into rejected_paper_orders table.
        Separates rejected trades completely from paper_orders to eliminate decision_id collision.
        """
        decision_val = decision if decision is not None else (direction or "UNKNOWN")
        now = datetime.now(timezone.utc).isoformat()
        ts_str = timestamp.isoformat() if timestamp else now
        rejection_id = str(uuid.uuid4())
        
        regime_val = regime if regime else "UNKNOWN"
        
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO rejected_paper_orders (
                            rejection_id, portfolio_id, decision_id, symbol, decision, 
                            reason, timestamp, strategy, regime, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (rejection_id, portfolio_id, decision_id, symbol, decision_val, 
                         reason, ts_str, strategy, regime_val, now)
                    )
                except sqlite3.IntegrityError as e:
                    logger.warning(f"Failed to record rejected trade {decision_id}: {e}")
                    pass # Already recorded

    def get_rejected_orders(self, portfolio_id: str, limit: int = 20) -> List[sqlite3.Row]:
        """
        Retrieves the read-only ledger of rejected orders for a portfolio, sorted by newest first.
        """
        from contextlib import closing
        with closing(self._get_conn()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM rejected_paper_orders WHERE portfolio_id = ? ORDER BY created_at DESC LIMIT ?",
                    (portfolio_id, limit)
                )
                return cursor.fetchall()
                    
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
        regime: Optional[str] = None,
        reason: str = "MANUAL_EXIT"
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
                         exit_price, ts_str, "FILLED", commission, slippage, now, reason, regime_val, strategy_val)
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
                         ts_str, actual_price, quantity, pnl, reason, strategy_val, regime_val, now)
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

    def set_death_mode_state(
        self,
        portfolio_id: str,
        active: bool,
        reason: Optional[str] = None,
        updated_at: Optional[datetime] = None
    ) -> None:
        """
        Atomically persists the per-portfolio Death Mode state.
        Uses parameterized SQL and atomic upsert (ON CONFLICT DO UPDATE).
        Raises PaperRepositoryException on failure.
        """
        now = updated_at.isoformat() if updated_at else datetime.now(timezone.utc).isoformat()
        active_int = 1 if active else 0
        from contextlib import closing
        try:
            with closing(self._get_conn()) as conn:
                with conn:
                    try:
                        conn.execute(
                            """
                            INSERT INTO paper_death_mode_state (portfolio_id, active, reason, updated_at)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(portfolio_id) DO UPDATE SET
                                active = excluded.active,
                                reason = excluded.reason,
                                updated_at = excluded.updated_at
                            """,
                            (portfolio_id, active_int, reason, now)
                        )
                    except sqlite3.OperationalError as op_err:
                        if "no such table" in str(op_err).lower():
                            conn.execute(
                                """
                                CREATE TABLE IF NOT EXISTS paper_death_mode_state (
                                    portfolio_id TEXT PRIMARY KEY,
                                    active BOOLEAN NOT NULL,
                                    reason TEXT,
                                    updated_at TEXT NOT NULL,
                                    FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
                                );
                                """
                            )
                            conn.execute(
                                """
                                INSERT INTO paper_death_mode_state (portfolio_id, active, reason, updated_at)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(portfolio_id) DO UPDATE SET
                                    active = excluded.active,
                                    reason = excluded.reason,
                                    updated_at = excluded.updated_at
                                """,
                                (portfolio_id, active_int, reason, now)
                            )
                        else:
                            raise
        except Exception as e:
            logger.error("Failed to persist death mode state for portfolio '%s': %s", portfolio_id, e)
            raise PaperRepositoryException(f"Failed to persist death mode state: {e}") from e

    def get_death_mode_state(self, portfolio_id: str) -> Optional[Dict[str, Any]]:
        """
        Loads the per-portfolio Death Mode state.
        Returns a dict with portfolio_id, active, is_active, reason, updated_at,
        or None if no state is recorded.
        """
        from contextlib import closing
        try:
            with closing(self._get_conn()) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "SELECT portfolio_id, active, reason, updated_at FROM paper_death_mode_state WHERE portfolio_id = ?",
                        (portfolio_id,)
                    )
                    row = cursor.fetchone()
                except sqlite3.OperationalError as op_err:
                    if "no such table" in str(op_err).lower():
                        return None
                    raise
                if not row:
                    return None
                return {
                    "portfolio_id": str(row["portfolio_id"]),
                    "active": bool(row["active"]),
                    "is_active": bool(row["active"]),
                    "reason": row["reason"],
                    "updated_at": row["updated_at"]
                }
        except Exception as e:
            logger.error("Failed to load death mode state for portfolio '%s': %s", portfolio_id, e)
            raise PaperRepositoryException(f"Failed to load death mode state: {e}") from e

    # Convenient aliases
    save_death_mode_state = set_death_mode_state
    load_death_mode_state = get_death_mode_state
