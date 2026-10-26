import uuid
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from app.config import config
from app.research.models import ResearchExperiment, ChampionChallengerResult
from app.research.registry import ExperimentRegistry

class ChampionChallengerValidator:
    def __init__(self, db_path: Optional[str] = None, require_persisted_evidence: bool = False):
        self.registry = ExperimentRegistry()
        self.db_path = db_path or config.DB_PATH
        self.require_persisted_evidence = require_persisted_evidence

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _extract_fold_metrics(fold) -> Tuple[int, float]:
        for attr in ["validation_report", "test_report"]:
            report = getattr(fold, attr, None)
            if report and getattr(report, "trade_metrics", None):
                tm = report.trade_metrics
                t = getattr(tm, "total_trades", 0)
                pf = getattr(tm, "profit_factor", 0.0)
                if t > 0:
                    return t, pf
        trades = getattr(fold, "trades", None)
        if trades is None:
            trades = getattr(fold, "total_trades", None)
        pf = getattr(fold, "profit_factor", None)
        if pf is None:
            pf = getattr(fold, "pf", None)
        if trades is not None:
            if pf is None:
                gp = getattr(fold, "gross_profit", 0.0) if hasattr(fold, "gross_profit") else (fold.get("gross_profit", 0.0) if isinstance(fold, dict) else 0.0)
                pf = float('inf') if gp > 0 else 0.0
            return trades, pf
        if isinstance(fold, dict):
            trades = fold.get("trades", fold.get("total_trades", 0))
            pf = fold.get("profit_factor", fold.get("pf", None))
            if pf is None:
                pf = float('inf') if fold.get("gross_profit", 0.0) > 0 else 0.0
            return trades, pf
        return 0, 0.0

    def evaluate(self, champion: ResearchExperiment, challenger: ResearchExperiment) -> ChampionChallengerResult:
        """
        Fair comparison between Champion and Challenger.
        Both must be COMPLETED experiments.
        """
        reasons = []
        decision = "INCONCLUSIVE"
        scorecard = {}

        if champion.status != "COMPLETED" or challenger.status != "COMPLETED":
            return ChampionChallengerResult(
                comparison_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc),
                champion_experiment_id=champion.experiment_id, challenger_experiment_id=challenger.experiment_id,
                dataset_id=champion.dataset_id, decision="INVALID",
                decision_reasons=["Both experiments must be COMPLETED."], scorecard={}
            )

        # 1. FAIR COMPARISON CHECK (Dataset, time, config assumptions)
        if champion.dataset_id != challenger.dataset_id:
            reasons.append("DATASET_MISMATCH")
        if champion.symbols != challenger.symbols:
            reasons.append("SYMBOL_MISMATCH")
        
        # Risk configs should be roughly identical in base limits
        champ_risk = champion.configuration_snapshot.get("risk_per_trade_pct")
        chall_risk = challenger.configuration_snapshot.get("risk_per_trade_pct")
        if champ_risk != chall_risk and champ_risk is not None and chall_risk is not None:
            reasons.append("RISK_MISMATCH")

        if reasons:
            return ChampionChallengerResult(
                comparison_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc),
                champion_experiment_id=champion.experiment_id, challenger_experiment_id=challenger.experiment_id,
                dataset_id=champion.dataset_id, decision="INVALID",
                decision_reasons=["Unfair comparison: " + ", ".join(reasons)], scorecard={}
            )

        # 2. METRICS COMPARISON (OOS)
        champ_oos = champion.out_of_sample_report
        chall_oos = challenger.out_of_sample_report

        if not champ_oos or not chall_oos:
            return ChampionChallengerResult(
                comparison_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc),
                champion_experiment_id=champion.experiment_id, challenger_experiment_id=challenger.experiment_id,
                dataset_id=champion.dataset_id, decision="INVALID",
                decision_reasons=["Missing OOS report"], scorecard={}
            )

        scorecard["oos_return"] = {"champ": champ_oos.equity_metrics.total_return_pct, "chall": chall_oos.equity_metrics.total_return_pct}
        scorecard["oos_drawdown"] = {"champ": champ_oos.equity_metrics.max_drawdown_pct, "chall": chall_oos.equity_metrics.max_drawdown_pct}
        scorecard["oos_trades"] = {"champ": champ_oos.trade_metrics.total_trades, "chall": chall_oos.trade_metrics.total_trades}
        scorecard["oos_win_rate"] = {"champ": champ_oos.trade_metrics.win_rate, "chall": chall_oos.trade_metrics.win_rate}
        scorecard["oos_profit_factor"] = {"champ": champ_oos.trade_metrics.profit_factor, "chall": chall_oos.trade_metrics.profit_factor}

        # 3. ROBUSTNESS & STRESS DEGRADATION (Phase 12 execution stress)
        champ_stress = {s.condition_name: s for s in champion.stress_test_results}
        chall_stress = {s.condition_name: s for s in challenger.stress_test_results}
        
        # Calculate max degradation across shared stress tests
        champ_max_deg = max([s.degradation_pct for s in champ_stress.values()]) if champ_stress else 0
        chall_max_deg = max([s.degradation_pct for s in chall_stress.values()]) if chall_stress else 0
        scorecard["max_stress_degradation"] = {"champ": champ_max_deg, "chall": chall_max_deg}

        # 4. WALK-FORWARD FOLD CONSISTENCY & SEVERE LOSS REJECTION
        chall_folds = getattr(challenger, "walk_forward_results", [])
        chall_artifact = getattr(challenger, "walk_forward_artifact", None)
        if not chall_folds and chall_artifact:
            chall_folds = getattr(chall_artifact, "folds", [])
        has_fold_evidence = bool(chall_folds)
        has_severe_loss = False
        severe_loss_details = []

        if not has_fold_evidence:
            reasons.append("Missing Walk-Forward Fold Evidence")
        else:
            for fold in chall_folds:
                trades, pf = self._extract_fold_metrics(fold)
                if trades > 0 and pf < 0.5:
                    has_severe_loss = True
                    severe_loss_details.append(f"PF={pf:.2f} ({trades} trades)")

            if has_severe_loss:
                reasons.append(f"Severe Loss in Validation Fold (PF < 0.5: {', '.join(severe_loss_details)})")

        scorecard["has_fold_evidence"] = has_fold_evidence
        scorecard["has_severe_loss"] = has_severe_loss

        # 4b. EVIDENCE PERSISTENCE INTEGRITY & RECONCILIATION
        persistence_failed = getattr(challenger, "persistence_failed", False)
        
        if chall_artifact:
            from app.research.robustness.artifact import verify_artifact_reconciliation
            is_rec, rec_issues = verify_artifact_reconciliation(chall_artifact)
            if not is_rec or not getattr(chall_artifact, "reconciled", True):
                persistence_failed = True
                reasons.append("Walk-Forward Evidence Reconciliation Mismatch")

        artifact_id = getattr(challenger, "artifact_id", None)
        strict_persistence = getattr(self, "require_persisted_evidence", False) or getattr(challenger, "require_persisted_evidence", False)
        if artifact_id or (strict_persistence and chall_artifact):
            target_id = artifact_id or getattr(chall_artifact, "artifact_id", None)
            from app.research.robustness.artifact import load_evidence_artifact
            loaded_art = load_evidence_artifact(target_id, self.db_path) if target_id else None
            if loaded_art is None:
                persistence_failed = True
                reasons.append(f"Walk-Forward Evidence Persistence Record Missing for {target_id}")

        if persistence_failed:
            reasons.append("Walk-Forward Evidence Persistence Failed")

        scorecard["persistence_failed"] = persistence_failed

        # 5. DECISION RULES (Anti-overfitting + Robustness boundaries)
        # Criteria for Promotion:
        # A. Must beat return
        # B. Must not increase drawdown unacceptably (>20% worse)
        # C. Must have acceptable sample size
        # D. Must not have severe degradation under stress (>50% worse than champion's degradation)
        # E. Must have walk-forward fold evidence (cannot produce PROMOTE without folds)
        # F. Must not have severe loss in any non-empty validation fold (PF < 0.5)
        # G. Must not have missing or failed evidence persistence
        
        ret_improved = chall_oos.equity_metrics.total_return_pct > champ_oos.equity_metrics.total_return_pct
        dd_degraded = chall_oos.equity_metrics.max_drawdown_pct > (champ_oos.equity_metrics.max_drawdown_pct * 1.2)
        trades_sufficient = chall_oos.trade_metrics.total_trades >= 30
        stress_acceptable = chall_max_deg <= (champ_max_deg + 20.0) # 20% margin
        
        if ret_improved:
            reasons.append("Higher OOS Return")
        else:
            reasons.append("Lower/Equal OOS Return")
            
        if dd_degraded:
            reasons.append("Unacceptable Drawdown Increase")
        
        if not trades_sufficient:
            reasons.append("Insufficient Sample Size (<30 trades)")
            
        if not stress_acceptable:
            reasons.append("Severe Stress Degradation")

        if has_severe_loss:
            decision = "REJECT"
        elif not has_fold_evidence:
            decision = "INCONCLUSIVE"
        elif persistence_failed:
            decision = "INCONCLUSIVE"
        elif ret_improved and not dd_degraded and trades_sufficient and stress_acceptable:
            decision = "PROMOTE"
        elif not trades_sufficient:
            decision = "INCONCLUSIVE"
        else:
            decision = "REJECT"

        # Construct final object
        result = ChampionChallengerResult(
            comparison_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc),
            champion_experiment_id=champion.experiment_id, challenger_experiment_id=challenger.experiment_id,
            dataset_id=champion.dataset_id, decision=decision,
            decision_reasons=reasons, scorecard=scorecard
        )
        return result

    def save_comparison(self, result: ChampionChallengerResult):
        """Persists the comparison to SQLite."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO champion_challenger (id, timestamp, champion_id, challenger_id, decision, comparison_json) VALUES (?, ?, ?, ?, ?, ?)",
                (result.comparison_id, result.timestamp.isoformat(), result.champion_experiment_id, result.challenger_experiment_id, result.decision, result.model_dump_json())
            )

    def get_comparison(self, comparison_id: str) -> Optional[ChampionChallengerResult]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT comparison_json FROM champion_challenger WHERE id = ?", (comparison_id,))
            row = cursor.fetchone()
            if row:
                return ChampionChallengerResult.model_validate_json(row[0])
        return None

    def list_comparisons(self) -> List[ChampionChallengerResult]:
        comparisons = []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT comparison_json FROM champion_challenger ORDER BY timestamp DESC")
            for row in cursor.fetchall():
                comparisons.append(ChampionChallengerResult.model_validate_json(row[0]))
        return comparisons
