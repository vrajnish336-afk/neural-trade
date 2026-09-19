import streamlit as st
from app.research.continuous_orchestrator import ContinuousResearchOrchestrator
from app.research.continuous_models import ResearchCycleState

def render_continuous_tab(conn):
    st.markdown("## PHASE 30: CONTINUOUS RESEARCH CONTROL CENTER")
    st.warning("PAPER / RESEARCH ONLY. CONTINUOUS RESEARCH ORCHESTRATION ONLY. NO LIVE TRADING.")
    
    orch = ContinuousResearchOrchestrator()
    
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Start / Tick Cycle"):
        active = orch.repo.get_active_cycle()
        if not active:
            orch.start_new_cycle()
        orch.tick()
        st.rerun()
        
    st.markdown("---")
    
    active = orch.repo.get_active_cycle()
    
    if active:
        st.markdown(f"### Active Cycle: `{active.cycle_id}`")
        
        status_color = "green" if active.state == ResearchCycleState.COMPLETED else ("red" if active.state in (ResearchCycleState.FAILED, ResearchCycleState.CANCELLED) else "orange")
        st.markdown(f"**State:** :{status_color}[{active.state.value}]")
        
        st.progress(len(active.completed_proposal_ids) / max(1, active.max_proposals))
        
        st.write(f"Generated Proposals: {len(active.generated_proposal_ids)} / {active.max_proposals}")
        st.write(f"Completed Validations: {len(active.completed_proposal_ids)}")
        
        if active.state == ResearchCycleState.WAITING_FOR_RESEARCH_APPROVAL:
            st.info("Cycle paused. Waiting for human research approval of proposals. Go to Tab 13 (Self-Evolution) to approve them, then click 'Start / Tick Cycle' here to resume.")
            
        c1, c2 = st.columns(2)
        if c1.button("Pause Cycle", key="pause"):
            orch.pause_cycle(active.cycle_id)
            st.rerun()
        if c2.button("Cancel Cycle", key="cancel"):
            orch.cancel_cycle(active.cycle_id)
            st.rerun()
            
    else:
        st.info("No active continuous research cycle.")
        
    st.markdown("---")
    st.markdown("### Historical Cycles")
    
    cycles = orch.repo.get_cycles()
    if cycles:
        import pandas as pd
        df = pd.DataFrame([{
            "Cycle ID": c.cycle_id,
            "State": c.state.value,
            "Proposals": len(c.generated_proposal_ids),
            "Completed": len(c.completed_proposal_ids),
            "Created At": c.created_at.isoformat()
        } for c in cycles])
        st.dataframe(df, use_container_width=True)
