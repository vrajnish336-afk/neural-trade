import os
import json
import uuid
import hashlib
import sqlite3
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import config
from app.core.models import MarketBar

class FoldBoundary(BaseModel):
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str

class FoldEvidenceMetrics(BaseModel):
    """
    Evidence metrics for an individual walk-forward fold.
    Note: gross_profit, gross_loss, and profit_factor represent post-cost metrics
    derived from closed trades whose realized PnL already incorporates entry/exit commissions
    and slippage.
    """
    window_id: int
    boundaries: FoldBoundary
    trades: int
    wins: int
    losses: int
    profit_factor: Optional[float] = 0.0
    expectancy: float
    max_drawdown_pct: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    entry_costs: float = 0.0
    exit_costs: float = 0.0
    slippage_costs: float = 0.0
    total_costs: float = 0.0

    @property
    def effective_profit_factor(self) -> float:
        if self.profit_factor is not None:
            return self.profit_factor
        return float('inf') if self.gross_profit > 0 else 0.0

    @property
    def post_cost_profit_factor(self) -> float:
        """Explicit label: post-cost profit factor."""
        return self.effective_profit_factor

    @property
    def post_cost_gross_profit(self) -> float:
        """Explicit label: post-cost gross profit (sum of winning trades net of costs)."""
        return self.gross_profit

    @property
    def post_cost_gross_loss(self) -> float:
        """Explicit label: post-cost gross loss (sum of losing trades inclusive of costs)."""
        return self.gross_loss

    @property
    def pre_cost_net_pnl(self) -> float:
        """Estimated pre-cost net PnL before execution fees and slippage."""
        return self.net_pnl + self.total_costs

    @property
    def is_cost_adjusted(self) -> bool:
        """Indicates that metrics are post-cost adjusted."""
        return True

class AggregateEvidenceMetrics(BaseModel):
    """
    Aggregate metrics across all completed walk-forward folds.
    Note: gross_profit, gross_loss, and profit_factor represent post-cost metrics.
    """
    total_trades: int
    wins: int
    losses: int
    profit_factor: Optional[float] = 0.0
    expectancy: float
    max_drawdown_pct: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    total_costs: float

    @property
    def effective_profit_factor(self) -> float:
        if self.profit_factor is not None:
            return self.profit_factor
        return float('inf') if self.gross_profit > 0 else 0.0

    @property
    def post_cost_profit_factor(self) -> float:
        """Explicit label: post-cost profit factor."""
        return self.effective_profit_factor

    @property
    def post_cost_gross_profit(self) -> float:
        """Explicit label: post-cost gross profit (sum of winning trades net of costs)."""
        return self.gross_profit

    @property
    def post_cost_gross_loss(self) -> float:
        """Explicit label: post-cost gross loss (sum of losing trades inclusive of costs)."""
        return self.gross_loss

    @property
    def pre_cost_net_pnl(self) -> float:
        """Estimated pre-cost net PnL before execution fees and slippage."""
        return self.net_pnl + self.total_costs

    @property
    def is_cost_adjusted(self) -> bool:
        """Indicates that metrics are post-cost adjusted."""
        return True

class WalkForwardEvidenceArtifact(BaseModel):
    artifact_id: str
    created_at: str
    candidate_id: str
    strategy_name: str
    parameters: Dict[str, Any]
    config_snapshot: Dict[str, Any] = {}
    dataset_fingerprint: str
    code_revision: str
    folds: List[FoldEvidenceMetrics]
    aggregate: AggregateEvidenceMetrics
    reconciled: bool = True
    reconciliation_notes: Optional[str] = None

def get_current_code_revision() -> str:
    """Retrieves current git commit hash, falling back gracefully."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=2
        )
        return res.stdout.strip()
    except Exception:
        return "unknown_rev"

def compute_dataset_fingerprint(bars: List[MarketBar], symbol: Optional[str] = None) -> str:
    """Computes a deterministic SHA-256 fingerprint for a sequence of market bars."""
    if not bars:
        return "empty_dataset"
    sym = symbol or bars[0].symbol
    start_t = min(b.timestamp for b in bars).isoformat()
    end_t = max(b.timestamp for b in bars).isoformat()
    count = len(bars)
    first_close = bars[0].close
    last_close = bars[-1].close
    h_input = f"{sym}_{start_t}_{end_t}_{count}_{first_close}_{last_close}"
    return hashlib.sha256(h_input.encode("utf-8")).hexdigest()

def verify_artifact_reconciliation(artifact: WalkForwardEvidenceArtifact) -> Tuple[bool, List[str]]:
    """
    Verifies that fold metrics reconcile with aggregate values in an artifact.
    Returns (is_reconciled, list_of_mismatch_reasons).
    """
    mismatches = []
    if not artifact.folds:
        return False, ["Artifact contains no folds."]

    sum_trades = sum(f.trades for f in artifact.folds)
    if sum_trades != artifact.aggregate.total_trades:
        mismatches.append(f"Trade count mismatch: folds ({sum_trades}) != aggregate ({artifact.aggregate.total_trades})")

    sum_wins = sum(f.wins for f in artifact.folds)
    sum_losses = sum(f.losses for f in artifact.folds)
    if sum_wins != artifact.aggregate.wins or sum_losses != artifact.aggregate.losses:
        mismatches.append(f"Wins/Losses mismatch: folds W/L ({sum_wins}/{sum_losses}) != aggregate ({artifact.aggregate.wins}/{artifact.aggregate.losses})")

    sum_gp = sum(f.gross_profit for f in artifact.folds)
    sum_gl = sum(f.gross_loss for f in artifact.folds)
    if abs(sum_gp - artifact.aggregate.gross_profit) > 1e-2:
        mismatches.append(f"Gross profit mismatch: folds ({sum_gp:.2f}) != aggregate ({artifact.aggregate.gross_profit:.2f})")
    if abs(sum_gl - artifact.aggregate.gross_loss) > 1e-2:
        mismatches.append(f"Gross loss mismatch: folds ({sum_gl:.2f}) != aggregate ({artifact.aggregate.gross_loss:.2f})")

    sum_net = sum(f.net_pnl for f in artifact.folds)
    if abs(sum_net - artifact.aggregate.net_pnl) > 1e-2:
        mismatches.append(f"Net PnL mismatch: folds ({sum_net:.2f}) != aggregate ({artifact.aggregate.net_pnl:.2f})")

    sum_costs = sum(f.total_costs for f in artifact.folds)
    if abs(sum_costs - artifact.aggregate.total_costs) > 1e-2:
        mismatches.append(f"Total costs mismatch: folds ({sum_costs:.2f}) != aggregate ({artifact.aggregate.total_costs:.2f})")

    return (len(mismatches) == 0), mismatches

def build_evidence_artifact(
    candidate_id: str,
    strategy_name: str,
    parameters: Dict[str, Any],
    dataset_fingerprint: str,
    folds: List[FoldEvidenceMetrics],
    aggregate: AggregateEvidenceMetrics,
    config_snapshot: Optional[Dict[str, Any]] = None,
    code_revision: Optional[str] = None,
    artifact_id: Optional[str] = None,
    created_at: Optional[str] = None
) -> WalkForwardEvidenceArtifact:
    """
    Constructs and reconciles a WalkForwardEvidenceArtifact.
    Enforces strict reconciliation between fold sums and aggregate values.
    """
    if not folds:
        raise ValueError("Cannot build evidence artifact with 0 folds: fold evidence is required.")

    candidate_art = WalkForwardEvidenceArtifact(
        artifact_id=artifact_id or str(uuid.uuid4()),
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        candidate_id=candidate_id,
        strategy_name=strategy_name,
        parameters=parameters,
        config_snapshot=config_snapshot or {},
        dataset_fingerprint=dataset_fingerprint,
        code_revision=code_revision or get_current_code_revision(),
        folds=folds,
        aggregate=aggregate,
        reconciled=True,
        reconciliation_notes="Fold totals perfectly reconciled with aggregate."
    )

    is_reconciled, issues = verify_artifact_reconciliation(candidate_art)
    if not is_reconciled:
        raise ValueError(f"Artifact reconciliation failure: {'; '.join(issues)}")

    return candidate_art

def save_evidence_artifact(
    artifact: WalkForwardEvidenceArtifact,
    db_path: Optional[str] = None,
    json_path: Optional[str] = None
) -> str:
    """Persists artifact to SQLite and/or JSON."""
    target_db = db_path or config.DB_PATH
    conn = sqlite3.connect(target_db)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS walk_forward_evidence (
                artifact_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                created_at TEXT,
                strategy_name TEXT,
                dataset_fingerprint TEXT,
                code_revision TEXT,
                reconciled INTEGER,
                artifact_json TEXT
            )
        """)
        conn.execute("""
            INSERT OR REPLACE INTO walk_forward_evidence (
                artifact_id, candidate_id, created_at, strategy_name,
                dataset_fingerprint, code_revision, reconciled, artifact_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            artifact.artifact_id,
            artifact.candidate_id,
            artifact.created_at,
            artifact.strategy_name,
            artifact.dataset_fingerprint,
            artifact.code_revision,
            1 if artifact.reconciled else 0,
            artifact.model_dump_json()
        ))
        conn.commit()
    finally:
        conn.close()

    if json_path:
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w") as f:
            f.write(artifact.model_dump_json(indent=2))

    return artifact.artifact_id

def load_evidence_artifact(artifact_id: str, db_path: Optional[str] = None) -> Optional[WalkForwardEvidenceArtifact]:
    """Loads a persisted artifact from SQLite by artifact_id."""
    target_db = db_path or config.DB_PATH
    if not os.path.exists(target_db):
        return None
    try:
        conn = sqlite3.connect(target_db)
    except Exception:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT artifact_json FROM walk_forward_evidence WHERE artifact_id = ?", (artifact_id,))
        row = cursor.fetchone()
        if row:
            art = WalkForwardEvidenceArtifact.model_validate_json(row[0])
            is_valid, _ = verify_artifact_reconciliation(art)
            if not is_valid:
                art.reconciled = False
            return art
        return None
    except sqlite3.OperationalError:
        return None
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

def load_evidence_from_json(json_path: str) -> Optional[WalkForwardEvidenceArtifact]:
    """Loads a persisted artifact from JSON file, verifying reconciliation integrity."""
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r") as f:
            art = WalkForwardEvidenceArtifact.model_validate_json(f.read())
            is_valid, _ = verify_artifact_reconciliation(art)
            if not is_valid:
                art.reconciled = False
            return art
    except Exception:
        return None
