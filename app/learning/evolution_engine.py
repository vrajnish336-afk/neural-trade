import uuid
import json
import logging
from typing import List, Optional, Dict, Any
from app.sandbox.repository import SandboxRepository
from app.sandbox.models import ResearchCodeProposal, ProposalStatus
from app.sandbox.service import SandboxService
from app.research.experiment_intelligence.service import ExperimentComparisonService
from app.learning.evolution_models import ResearchEvolutionProposal, EvolutionProposalState, ResearchAnswer
from app.learning.evolution_repository import EvolutionRepository
from app.learning.repository import LearningRepository

logger = logging.getLogger(__name__)

class ResearchGapDetector:
    def __init__(self):
        self.sandbox_repo = SandboxRepository()
        
    def detect_gaps(self) -> List[dict]:
        gaps = []
        exps = self.sandbox_repo._get_conn().execute("SELECT experiment_id, backtest_result_json FROM research_sandbox_experiments").fetchall()
        for e in exps:
            exp_id = e[0]
            bt = e[1]
            if bt:
                bt_data = json.loads(bt)
                trades = bt_data.get("number_of_trades", 0)
                if trades < 30:
                    gaps.append({
                        "experiment_id": exp_id,
                        "gap_type": "SAMPLE_SIZE_WEAK",
                        "description": f"Experiment {exp_id} has {trades} trades (needs >30)."
                    })
        return gaps

class ControlledEvolutionEngine:
    def __init__(self):
        self.repo = EvolutionRepository()
        self.sandbox_repo = SandboxRepository()
        self.sandbox_svc = SandboxService()
        self.compare_svc = ExperimentComparisonService()
        self.learning_repo = LearningRepository()
        self.gap_detector = ResearchGapDetector()
        
    def _validate_bounds(self, baseline: Dict[str, Any], proposed: Dict[str, Any]) -> bool:
        """Ensure no arbitrary keys and types remain bounded."""
        for k, v in proposed.items():
            if k not in baseline: return False
            if type(v) != type(baseline[k]): return False
            if isinstance(v, (int, float)) and v <= 0: return False
        return True
        
    def generate_proposal(self, baseline_exp_id: str, proposed_params: Dict[str, Any], question: str, rationale: str) -> Optional[ResearchEvolutionProposal]:
        base_exp = self.sandbox_repo.get_experiment(baseline_exp_id)
        if not base_exp: return None
        
        if not self._validate_bounds(base_exp.parameters, proposed_params):
            logger.warning("Rejected by safety bounds.")
            return None
            
        proposal = ResearchEvolutionProposal(
            proposal_id=str(uuid.uuid4()),
            baseline_experiment_id=baseline_exp_id,
            research_question=question,
            rationale=rationale,
            baseline_parameters=base_exp.parameters,
            proposed_parameters=proposed_params,
            state=EvolutionProposalState.REVIEW_REQUIRED
        )
        
        # Duplicate detection
        ident = proposal.get_identity_hash()
        for p in self.repo.get_proposals():
            if p.get_identity_hash() == ident:
                logger.warning("Duplicate proposal rejected.")
                return None
                
        self.repo.save_proposal(proposal)
        return proposal

    def approve_proposal(self, proposal_id: str) -> bool:
        p = self.repo.get_proposal(proposal_id)
        if p and p.state == EvolutionProposalState.REVIEW_REQUIRED:
            p.state = EvolutionProposalState.APPROVED_FOR_RESEARCH
            self.repo.save_proposal(p)
            return True
        return False
        
    def execute_proposal(self, proposal_id: str) -> bool:
        """Executes an approved evolution proposal as a new sandbox experiment."""
        p = self.repo.get_proposal(proposal_id)
        if not p or p.state != EvolutionProposalState.APPROVED_FOR_RESEARCH:
            return False
            
        base_exp = self.sandbox_repo.get_experiment(p.baseline_experiment_id)
        if not base_exp: return False
        
        # We need the original proposal code for the sandbox wrapper
        orig_prop = self.sandbox_repo._get_conn().execute("SELECT code, entrypoint FROM research_code_proposals WHERE proposal_id=?", (base_exp.proposal_id,)).fetchone()
        if not orig_prop: return False
        
        code = orig_prop[0]
        entrypoint = orig_prop[1]
        
        new_sandbox_prop = self.sandbox_svc.propose_code(
            f"Evol_{p.proposal_id}", entrypoint, p.rationale, code
        )
        new_sandbox_prop.status = ProposalStatus.SANDBOX_READY
        self.sandbox_repo.save_proposal(new_sandbox_prop)
        
        # Reconstruct bars for a simple run
        # In a real run, this fetches dataset_identity
        from app.core.models import MarketBar
        from datetime import datetime, timezone
        bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=1, low=1, close=1, volume=1)]
        
        exp = self.sandbox_svc.run_backtest(new_sandbox_prop, base_exp.dataset_identity, bars, p.proposed_parameters)
        
        p.new_experiment_id = exp.experiment_id
        p.state = EvolutionProposalState.EXPERIMENT_CREATED
        self.repo.save_proposal(p)
        return True

    def validate_experiment(self, proposal_id: str) -> bool:
        """Runs the comparison engine to answer the research question."""
        p = self.repo.get_proposal(proposal_id)
        if not p or p.state != EvolutionProposalState.EXPERIMENT_CREATED:
            return False
            
        comp = self.compare_svc.compare_experiments(p.baseline_experiment_id, p.new_experiment_id)
        if not comp: return False
        
        p.comparison_id = comp.comparison_id
        p.state = EvolutionProposalState.VALIDATED
        
        # Answer resolution based on simple heuristic
        if comp.performance_winner == p.new_experiment_id and comp.coverage_winner == p.new_experiment_id:
            p.final_research_answer = ResearchAnswer.SUPPORTED
        elif comp.performance_winner == p.baseline_experiment_id:
            p.final_research_answer = ResearchAnswer.NOT_SUPPORTED
        else:
            p.final_research_answer = ResearchAnswer.INCONCLUSIVE
            
        self.repo.save_proposal(p)
        return True
