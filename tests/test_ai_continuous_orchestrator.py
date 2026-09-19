import pytest
from app.research.continuous_orchestrator import ContinuousResearchOrchestrator
from app.research.continuous_models import ResearchCycleState
from app.learning.evolution_models import EvolutionProposalState
from app.sandbox.models import ResearchSandboxExperiment

@pytest.fixture
def orch():
    o = ContinuousResearchOrchestrator()
    o.repo._init_db()
    o.evolution_engine.repo._init_db()
    o.sandbox_repo._init_db()
    active = o.repo.get_active_cycle()
    if active:
        o.cancel_cycle(active.cycle_id)
    with o.sandbox_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_sandbox_experiments")
    return o

def test_start_new_cycle(orch):
    # Ensure no cycle initially
    assert orch.repo.get_active_cycle() is None
    
    # Start cycle
    cycle = orch.start_new_cycle()
    assert cycle is not None
    assert cycle.state == ResearchCycleState.DISCOVERING
    
    # Cannot start a second active cycle
    cycle2 = orch.start_new_cycle()
    assert cycle2 is None

def test_tick_cycle_with_no_gaps(orch):
    cycle = orch.start_new_cycle()
    # If no gaps are detected, it should just complete
    orch.tick()
    
    updated_cycle = orch.repo.get_cycle(cycle.cycle_id)
    assert updated_cycle.state == ResearchCycleState.COMPLETED

def test_cycle_waits_for_approval(orch):
    import uuid
    from app.research.planner.repository import PlannerRepository
    from app.research.planner.models import ResearchDecision, ResearchQuestionCandidate, ResearchDecisionState, ResearchAction, ResearchPriorityBreakdown
    from datetime import datetime, timezone
    from app.research.evidence_graph.repository import EvidenceGraphRepository
    from app.research.evidence_graph.models import EvidenceNode, NodeType
    
    t = datetime.now(timezone.utc)
    exp_id = str(uuid.uuid4())
    gap_id = str(uuid.uuid4())
    decision_id = str(uuid.uuid4())
    q_id = str(uuid.uuid4())
    
    # Setup mock sandbox experiment
    exp = ResearchSandboxExperiment(
        experiment_id=exp_id,
        proposal_id="pmock",
        code_hash="c1",
        dataset_identity="ds1",
        parameters={"lookback": 20},
        backtest_result_json='{"number_of_trades": 15}'
    )
    orch.sandbox_repo.save_experiment(exp)
    
    graph_repo = EvidenceGraphRepository()
    graph_repo.save_node(EvidenceNode(node_id=gap_id, node_type=NodeType.EVIDENCE_GAP, source_id=exp_id, source_type="t", identity_hash="idh", created_at=t, as_of=t))
    
    planner_repo = PlannerRepository()
    planner_repo.save_candidate(ResearchQuestionCandidate(question_id=q_id, research_identity="idh", research_question="test q", originating_gap=gap_id, status=ResearchDecisionState.DISCOVERED, created_at=t, as_of=t))
    
    planner_repo.save_decision(ResearchDecision(
        decision_id=decision_id,
        research_question_id=q_id,
        recommended_action=ResearchAction.RESEARCH_NOW,
        priority=3.0,
        priority_breakdown=ResearchPriorityBreakdown(),
        status=ResearchDecisionState.APPROVED_FOR_RESEARCH,
        created_at=t,
        as_of=t
    ))

    cycle = orch.start_new_cycle()
    orch.tick() # Should discover decision and generate proposal

    updated = orch.repo.get_cycle(cycle.cycle_id)
    assert updated.state == ResearchCycleState.WAITING_FOR_RESEARCH_APPROVAL
    assert len(updated.generated_proposal_ids) > 0
    
    # Tick again without approval
    orch.tick()
    updated = orch.repo.get_cycle(cycle.cycle_id)
    assert updated.state == ResearchCycleState.WAITING_FOR_RESEARCH_APPROVAL # Still waiting
    
    # Approve
    pid = updated.generated_proposal_ids[0]
    orch.evolution_engine.approve_proposal(pid)
    
    # Tick again
    orch.tick()
    updated = orch.repo.get_cycle(cycle.cycle_id)
    assert updated.state == ResearchCycleState.EXECUTING_EXPERIMENTS

def test_pause_resume(orch):
    cycle = orch.start_new_cycle()
    assert orch.pause_cycle(cycle.cycle_id) == True
    
    c = orch.repo.get_cycle(cycle.cycle_id)
    assert c.state == ResearchCycleState.PAUSED
    
    # Tick does nothing
    assert orch.tick() == False
    
    assert orch.resume_cycle(cycle.cycle_id) == True
    c = orch.repo.get_cycle(cycle.cycle_id)
    assert c.state == ResearchCycleState.DISCOVERING
