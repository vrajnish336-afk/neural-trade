import uuid
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.config import config
from app.research.models import ResearchExperiment, ChampionChallengerResult
from app.research.registry import ExperimentRegistry

class ChampionChallengerValidator:
    def __init__(self):
        self.registry = ExperimentRegistry()
        self.db_path = config.DB_PATH

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

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

        # 4. DECISION RULES (Anti-overfitting + Robustness boundaries)
        # Criteria for Promotion:
        # A. Must beat return
        # B. Must not increase drawdown unacceptably (>20% worse)
        # C. Must have acceptable sample size
        # D. Must not have severe degradation under stress (>50% worse than champion's degradation)
        
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

        if ret_improved and not dd_degraded and trades_sufficient and stress_acceptable:
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
