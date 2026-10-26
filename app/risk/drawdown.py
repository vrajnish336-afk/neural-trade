"""
Portfolio Drawdown Service — Phase 58
======================================
Computes portfolio drawdown metrics from persisted equity snapshots.
All calculations are purely deterministic.  No I/O.  No side-effects.

Formula:
    drawdown_pct = ((running_peak - current_equity) / running_peak) * 100

Accounting basis:
    paper_equity_snapshots records are stored atomically at every entry order
    (post-commission deduction) and every exit (post-net-PnL realisation).
    The equity value is cash-based — it does NOT include unrealised open-
    position mark-to-market.  Therefore drawdown reflects realised changes
    to the account, not floating P&L.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class DrawdownStatus(str, Enum):
    OK = "OK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"   # fewer than 2 valid snapshots
    INVALID_DATA = "INVALID_DATA"             # negative/zero peak, malformed rows


@dataclass(frozen=True)
class DrawdownResult:
    """Immutable container for drawdown metrics."""
    status: DrawdownStatus

    # Only populated when status == OK
    current_drawdown_pct: float = 0.0        # (peak - current) / peak * 100
    max_drawdown_pct: float = 0.0            # worst ever observed in window
    running_peak_equity: float = 0.0         # highest equity seen so far
    current_equity: float = 0.0             # last snapshot value
    observation_start: Optional[str] = None  # ISO timestamp of first snapshot
    observation_end: Optional[str] = None    # ISO timestamp of last snapshot
    snapshot_count: int = 0
    has_partial_history: bool = False        # True when snapshots don't reach t=0
    reason: str = ""                         # populated on non-OK status


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DrawdownService:
    """
    Calculates drawdown metrics from an ordered sequence of equity snapshot rows.

    Each row must expose (at minimum):
        row['timestamp']       — ISO-8601 string
        row['current_equity']  — float >= 0

    The service is stateless; call ``calculate()`` as many times as needed.
    """

    def calculate(
        self,
        snapshots: Sequence,
        *,
        has_partial_history: bool = False,
        current_equity: Optional[float] = None,
        as_of: Optional[str] = None,
    ) -> DrawdownResult:
        """
        Args:
            snapshots: Ordered (ASC timestamp) sequence of sqlite3.Row-like
                       objects from ``PaperRepository.get_equity_snapshots()``.
            has_partial_history: Caller signals that the snapshot window does
                       not extend back to portfolio creation (e.g. legacy data).
            current_equity: Optional true dynamic equity (Realized Cash + Combined
                       unrealized PnL of open positions) evaluated at current market prices.
            as_of: Optional ISO-8601 timestamp representing current evaluation time.

        Returns:
            DrawdownResult with status OK or an error sentinel.
        """
        if (not snapshots or len(snapshots) < 1) and current_equity is None:
            return DrawdownResult(
                status=DrawdownStatus.INSUFFICIENT_DATA,
                reason=f"Need at least 2 snapshots, got {len(snapshots) if snapshots else 0}.",
            )

        # ------------------------------------------------------------------
        # 1. Parse and validate each snapshot row
        # ------------------------------------------------------------------
        rows: List[dict] = []
        for raw in (snapshots or []):
            try:
                ts = str(raw["timestamp"]).strip()
                equity = float(raw["current_equity"])
                try:
                    unrealized = float(raw["unrealized_pnl"])
                    cash = float(raw["current_cash"])
                    if abs(equity - cash) < 1e-6 and unrealized != 0.0:
                        equity = cash + unrealized
                except (KeyError, IndexError, TypeError, ValueError):
                    pass

                if not ts:
                    logger.warning("Drawdown: skipping row with empty timestamp.")
                    continue
                rows.append({"timestamp": ts, "equity": equity})
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Drawdown: malformed snapshot row skipped — %s", exc)

        # ------------------------------------------------------------------
        # 2. Sort chronologically (guard against storage order anomalies)
        # ------------------------------------------------------------------
        rows.sort(key=lambda r: r["timestamp"])

        # ------------------------------------------------------------------
        # 2b. Integrate live current dynamic equity if provided
        # ------------------------------------------------------------------
        if current_equity is not None:
            try:
                eq_val = float(current_equity)
                ts_val = str(as_of).strip() if as_of else None
                if not ts_val:
                    from datetime import datetime, timezone
                    ts_val = datetime.now(timezone.utc).isoformat()
                rows.append({"timestamp": ts_val, "equity": eq_val})
            except (TypeError, ValueError) as exc:
                logger.warning("Drawdown: malformed current_equity skipped — %s", exc)

        if len(rows) < 2:
            return DrawdownResult(
                status=DrawdownStatus.INSUFFICIENT_DATA,
                reason=f"Need at least 2 snapshots or valid observations, got {len(rows)}.",
            )

        # ------------------------------------------------------------------
        # 3. Validate the initial peak is positive (no division by zero)
        # ------------------------------------------------------------------
        first_equity = rows[0]["equity"]
        if first_equity <= 0:
            return DrawdownResult(
                status=DrawdownStatus.INVALID_DATA,
                reason=f"Initial equity snapshot is non-positive ({first_equity}). Cannot calculate drawdown.",
            )

        # ------------------------------------------------------------------
        # 4. Walk the series — O(n), single pass
        # ------------------------------------------------------------------
        running_peak = first_equity
        max_dd_pct = 0.0

        for row in rows[1:]:
            eq = row["equity"]
            if eq <= 0:
                # Non-positive equity is anomalous or total loss; log and continue
                logger.warning(
                    "Drawdown: non-positive equity value (%s) at %s — skipped in peak tracking.",
                    eq, row["timestamp"]
                )
                if running_peak > 0:
                    max_dd_pct = max(max_dd_pct, 100.0)
                continue

            if eq > running_peak:
                running_peak = eq

            if running_peak > 0:
                dd = (running_peak - eq) / running_peak * 100.0
                if dd > max_dd_pct:
                    max_dd_pct = dd

        # ------------------------------------------------------------------
        # 5. Current drawdown uses the LAST equity observation (including open losses)
        # ------------------------------------------------------------------
        last_equity = rows[-1]["equity"]
        if last_equity <= 0:
            last_valid_equity = last_equity
            current_dd_pct = 100.0
            max_dd_pct = max(max_dd_pct, 100.0)
        else:
            last_valid_equity = None
            for row in reversed(rows):
                if row["equity"] > 0:
                    last_valid_equity = row["equity"]
                    break

            if last_valid_equity is None or running_peak <= 0:
                return DrawdownResult(
                    status=DrawdownStatus.INVALID_DATA,
                    reason="Could not determine a valid running peak or current equity.",
                )

            current_dd_pct = (running_peak - last_valid_equity) / running_peak * 100.0
            current_dd_pct = max(0.0, current_dd_pct)   # clamp — peak may equal equity

        return DrawdownResult(
            status=DrawdownStatus.OK,
            current_drawdown_pct=round(current_dd_pct, 4),
            max_drawdown_pct=round(max_dd_pct, 4),
            running_peak_equity=round(running_peak, 4),
            current_equity=round(last_valid_equity, 4),
            observation_start=rows[0]["timestamp"],
            observation_end=rows[-1]["timestamp"],
            snapshot_count=len(rows),
            has_partial_history=has_partial_history,
            reason="",
        )
