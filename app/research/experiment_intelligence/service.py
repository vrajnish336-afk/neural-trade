import uuid
import json
import logging
from typing import Optional, List
from datetime import datetime
from app.sandbox.repository import SandboxRepository
from app.sandbox.models import ResearchSandboxExperiment
from app.research.experiment_intelligence.models import (
    ExperimentComparison, ExperimentEvidenceProfile,
    CompatibilityStatus, EvidenceStrength
)
from app.research.experiment_intelligence.repository import ExperimentComparisonRepository

logger = logging.getLogger(__name__)

class ExperimentComparisonService:
    def __init__(self):
        self.sandbox_repo = SandboxRepository()
        self.compare_repo = ExperimentComparisonRepository()
        
    def _check_compatibility(self, exp_a: ResearchSandboxExperiment, exp_b: ResearchSandboxExperiment) -> tuple[CompatibilityStatus, List[str]]:
        notes = []
        status = CompatibilityStatus.DIRECTLY_COMPARABLE
        
        if exp_a.dataset_identity != exp_b.dataset_identity:
            notes.append(f"Datasets differ: {exp_a.dataset_identity} vs {exp_b.dataset_identity}")
            status = CompatibilityStatus.NOT_COMPARABLE
            
        if exp_a.parameters != exp_b.parameters:
            notes.append("Parameters differ, which is typical for strategy comparisons.")
            if status == CompatibilityStatus.DIRECTLY_COMPARABLE:
                status = CompatibilityStatus.PARTIALLY_COMPARABLE
                
        return status, notes

    def _build_profile(self, exp: ResearchSandboxExperiment) -> ExperimentEvidenceProfile:
        import json
        
        # Base limits
        code_hash = exp.code_hash
        dataset_id = exp.dataset_identity
        
        # We need to parse backtest_result_json if available to get performance & coverage
        # Default fallback
        ret = 0.0
        dd = 0.0
        pf = 1.0
        trades = 0
        
        if exp.backtest_result_json:
            try:
                bt_data = json.loads(exp.backtest_result_json)
                ret = bt_data.get("total_return_pct", 0.0)
                dd = bt_data.get("max_drawdown_pct", 0.0)
                pf = bt_data.get("profit_factor", 1.0)
                trades = bt_data.get("number_of_trades", 0)
            except Exception as e:
                logger.error(f"Failed to parse backtest JSON for profile: {e}")

        # Stubbing robust evidence for now. In a full production run, we'd query RobustnessRepository.
        # Here we mock mapping based on trades limit to show intelligent sample-size handling.
        coverage_adequate = trades > 30
        
        if coverage_adequate:
            overall = EvidenceStrength.MODERATE
            seed_stab = EvidenceStrength.NOT_AVAILABLE
        else:
            overall = EvidenceStrength.INSUFFICIENT
            seed_stab = EvidenceStrength.NOT_AVAILABLE

        if ret > 0.1 and coverage_adequate:
            overall = EvidenceStrength.STRONG
            
        return ExperimentEvidenceProfile(
            experiment_id=exp.experiment_id,
            code_hash=code_hash,
            dataset_identity=dataset_id,
            parameters=exp.parameters,
            performance_return_pct=ret,
            performance_drawdown_pct=dd,
            performance_profit_factor=pf,
            robustness_seed_stability=seed_stab,
            robustness_cost_resilience=EvidenceStrength.NOT_AVAILABLE,
            robustness_parameter_sensitivity=EvidenceStrength.NOT_AVAILABLE,
            robustness_monte_carlo=EvidenceStrength.NOT_AVAILABLE,
            coverage_sample_size=trades,
            coverage_regimes_tested=1,
            coverage_is_adequate=coverage_adequate,
            reproducibility_deterministic=True,
            overall_strength=overall
        )

    def compare_experiments(self, exp_a_id: str, exp_b_id: str) -> Optional[ExperimentComparison]:
        exp_a = self.sandbox_repo.get_experiment(exp_a_id)
        exp_b = self.sandbox_repo.get_experiment(exp_b_id)
        
        if not exp_a or not exp_b:
            logger.error("Could not find one or both experiments.")
            return None
            
        compat, notes = self._check_compatibility(exp_a, exp_b)
        
        prof_a = self._build_profile(exp_a)
        prof_b = self._build_profile(exp_b)
        
        # Compare multidimensionally
        perf_winner = None
        if prof_a.performance_return_pct > prof_b.performance_return_pct:
            perf_winner = exp_a_id
        elif prof_b.performance_return_pct > prof_a.performance_return_pct:
            perf_winner = exp_b_id
            
        cov_winner = None
        if prof_a.coverage_sample_size > prof_b.coverage_sample_size:
            cov_winner = exp_a_id
        elif prof_b.coverage_sample_size > prof_a.coverage_sample_size:
            cov_winner = exp_b_id

        # Research Recommendation (NO BUY/SELL)
        if compat == CompatibilityStatus.NOT_COMPARABLE:
            rec = "Experiments are not comparable. Datasets differ."
            final_assessment = EvidenceStrength.INSUFFICIENT
        else:
            if prof_a.overall_strength == EvidenceStrength.STRONG and prof_b.overall_strength != EvidenceStrength.STRONG:
                rec = f"Experiment A ({exp_a_id}) has stronger evidence coverage under the evaluated conditions."
                final_assessment = EvidenceStrength.STRONG
            elif prof_b.overall_strength == EvidenceStrength.STRONG and prof_a.overall_strength != EvidenceStrength.STRONG:
                rec = f"Experiment B ({exp_b_id}) has stronger evidence coverage under the evaluated conditions."
                final_assessment = EvidenceStrength.STRONG
            else:
                rec = "Neither candidate clearly dominates the other in evidence breadth."
                final_assessment = EvidenceStrength.MIXED

        comp = ExperimentComparison(
            comparison_id=str(uuid.uuid4()),
            experiment_a_id=exp_a_id,
            experiment_b_id=exp_b_id,
            compatibility=compat,
            compatibility_notes=notes,
            profile_a=prof_a,
            profile_b=prof_b,
            robustness_winner=None,
            performance_winner=perf_winner,
            coverage_winner=cov_winner,
            final_research_assessment=final_assessment,
            recommendation=rec
        )
        
        self.compare_repo.save_comparison(comp)
        return comp
