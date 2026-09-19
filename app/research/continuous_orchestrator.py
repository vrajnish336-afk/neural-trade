import logging
import uuid
from typing import Optional
from app.research.continuous_models import ResearchCycle, ResearchCycleState
from app.research.continuous_repository import ContinuousRepository
from app.learning.evolution_engine import ControlledEvolutionEngine
from app.learning.evolution_models import EvolutionProposalState
from app.sandbox.repository import SandboxRepository

logger = logging.getLogger(__name__)

class ContinuousResearchOrchestrator:
    def __init__(self):
        self.repo = ContinuousRepository()
        self.evolution_engine = ControlledEvolutionEngine()
        self.sandbox_repo = SandboxRepository()
        
    def start_new_cycle(self) -> Optional[ResearchCycle]:
        active = self.repo.get_active_cycle()
        if active:
            logger.warning("Active cycle already exists. Cannot start a new one.")
            return None
            
        cycle = ResearchCycle(cycle_id=str(uuid.uuid4()))
        cycle.state = ResearchCycleState.DISCOVERING
        self.repo.save_cycle(cycle)
        return cycle
        
    def tick(self) -> bool:
        """Progresses the active research cycle one step."""
        cycle = self.repo.get_active_cycle()
        if not cycle: return False
        
        if cycle.state == ResearchCycleState.PAUSED:
            return False
            
        try:
            if cycle.state == ResearchCycleState.DISCOVERING:
                self._run_discovery(cycle)
            elif cycle.state == ResearchCycleState.WAITING_FOR_RESEARCH_APPROVAL:
                self._check_approvals(cycle)
            elif cycle.state == ResearchCycleState.EXECUTING_EXPERIMENTS:
                self._execute_experiments(cycle)
            elif cycle.state == ResearchCycleState.VALIDATING:
                self._validate_experiments(cycle)
                
            self.repo.save_cycle(cycle)
            return True
        except Exception as e:
            logger.error(f"Cycle {cycle.cycle_id} failed: {e}")
            cycle.state = ResearchCycleState.FAILED
            cycle.failure_reason = str(e)
            self.repo.save_cycle(cycle)
            return False
            
    def _run_discovery(self, cycle: ResearchCycle):
        from app.research.planner.repository import PlannerRepository
        from app.research.planner.models import ResearchDecisionState
        planner_repo = PlannerRepository()
        
        # Pull APPROVED_FOR_RESEARCH decisions
        approved_decisions = [d for d in planner_repo.get_ranked_decisions() if d.status == ResearchDecisionState.APPROVED_FOR_RESEARCH]
        
        if not approved_decisions:
            cycle.state = ResearchCycleState.COMPLETED
            return
            
        # Limit to budget
        budget_remaining = cycle.max_proposals - len(cycle.generated_proposal_ids)
        if budget_remaining <= 0:
            cycle.state = ResearchCycleState.BUDGET_EXHAUSTED
            return
            
        for decision in approved_decisions[:budget_remaining]:
            candidate = planner_repo.get_candidate(decision.research_question_id)
            if not candidate or not candidate.originating_gap:
                continue
                
            gap_node_id = candidate.originating_gap
            
            # Find the original experiment related to the gap
            # Normally we fetch gap from graph and find its source experiment
            from app.research.evidence_graph.repository import EvidenceGraphRepository
            graph_repo = EvidenceGraphRepository()
            gap_node = graph_repo.get_node(gap_node_id)
            if not gap_node: continue
            
            exp_id = gap_node.source_id
            base_exp = self.sandbox_repo.get_experiment(exp_id)
            if not base_exp: continue
            
            proposed = dict(base_exp.parameters)
            if "lookback" in proposed:
                proposed["lookback"] = max(1, proposed["lookback"] - 2)
                
            prop = self.evolution_engine.generate_proposal(
                baseline_exp_id=exp_id,
                proposed_params=proposed,
                question=candidate.research_question,
                rationale=f"Planner Decision: {decision.rationale}"
            )
            if prop:
                cycle.generated_proposal_ids.append(prop.proposal_id)
                # Mark decision as QUEUED
                decision.status = ResearchDecisionState.QUEUED
                planner_repo.save_decision(decision)
                
        if cycle.generated_proposal_ids:
            cycle.state = ResearchCycleState.WAITING_FOR_RESEARCH_APPROVAL
        else:
            cycle.state = ResearchCycleState.COMPLETED
            
    def _check_approvals(self, cycle: ResearchCycle):
        all_approved_or_done = True
        has_executable = False
        
        for pid in cycle.generated_proposal_ids:
            if pid in cycle.completed_proposal_ids: continue
            p = self.evolution_engine.repo.get_proposal(pid)
            if not p: continue
            
            if p.state == EvolutionProposalState.REVIEW_REQUIRED:
                all_approved_or_done = False
            elif p.state == EvolutionProposalState.APPROVED_FOR_RESEARCH:
                has_executable = True
                
        if all_approved_or_done and has_executable:
            cycle.state = ResearchCycleState.EXECUTING_EXPERIMENTS
        elif all_approved_or_done and not has_executable:
            # Maybe they were rejected
            cycle.state = ResearchCycleState.COMPLETED

    def _execute_experiments(self, cycle: ResearchCycle):
        all_executed = True
        for pid in cycle.generated_proposal_ids:
            if pid in cycle.completed_proposal_ids: continue
            p = self.evolution_engine.repo.get_proposal(pid)
            if not p: continue
            
            if p.state == EvolutionProposalState.APPROVED_FOR_RESEARCH:
                success = self.evolution_engine.execute_proposal(pid)
                if not success:
                    all_executed = False
            elif p.state == EvolutionProposalState.EXPERIMENT_CREATED:
                pass # Already executed
            elif p.state == EvolutionProposalState.REVIEW_REQUIRED:
                # Reverted? Wait
                all_executed = False
                
        if all_executed:
            cycle.state = ResearchCycleState.VALIDATING
            
    def _validate_experiments(self, cycle: ResearchCycle):
        all_validated = True
        for pid in cycle.generated_proposal_ids:
            if pid in cycle.completed_proposal_ids: continue
            p = self.evolution_engine.repo.get_proposal(pid)
            if not p: continue
            
            if p.state == EvolutionProposalState.EXPERIMENT_CREATED:
                success = self.evolution_engine.validate_experiment(pid)
                if success:
                    cycle.completed_proposal_ids.append(pid)
                else:
                    all_validated = False
            elif p.state == EvolutionProposalState.VALIDATED:
                if pid not in cycle.completed_proposal_ids:
                    cycle.completed_proposal_ids.append(pid)
                    
        if all_validated:
            cycle.state = ResearchCycleState.COMPLETED

    def pause_cycle(self, cycle_id: str) -> bool:
        c = self.repo.get_cycle(cycle_id)
        if c and c.state not in (ResearchCycleState.COMPLETED, ResearchCycleState.FAILED, ResearchCycleState.CANCELLED):
            c.state = ResearchCycleState.PAUSED
            self.repo.save_cycle(c)
            return True
        return False
        
    def resume_cycle(self, cycle_id: str) -> bool:
        c = self.repo.get_cycle(cycle_id)
        if c and c.state == ResearchCycleState.PAUSED:
            c.state = ResearchCycleState.DISCOVERING # Safe to jump back here, it will quickly traverse states
            self.repo.save_cycle(c)
            return True
        return False
        
    def cancel_cycle(self, cycle_id: str) -> bool:
        c = self.repo.get_cycle(cycle_id)
        if c and c.state not in (ResearchCycleState.COMPLETED, ResearchCycleState.FAILED, ResearchCycleState.CANCELLED):
            c.state = ResearchCycleState.CANCELLED
            self.repo.save_cycle(c)
            return True
        return False
