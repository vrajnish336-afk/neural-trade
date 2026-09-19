import streamlit as st
import json
from app.learning.evolution_engine import ControlledEvolutionEngine
from app.learning.evolution_models import EvolutionProposalState, ResearchAnswer

def render_evolution_tab(conn):
    st.markdown("## PHASE 29: SELF-EVOLUTION LAB")
    st.warning("PAPER / RESEARCH ONLY. CONTROLLED SELF-EVOLUTION ONLY. NO AUTOMATIC STRATEGY DEPLOYMENT.")
    
    engine = ControlledEvolutionEngine()
    
    st.markdown("### CURRENT RESEARCH STATE")
    gaps = engine.gap_detector.detect_gaps()
    st.write(f"Detected Evidence Gaps: {len(gaps)}")
    for g in gaps:
        st.info(f"[{g['gap_type']}] {g['description']}")
        
    st.markdown("---")
    st.markdown("### RESEARCH PROPOSALS")
    
    proposals = engine.repo.get_proposals()
    
    for p in proposals:
        with st.expander(f"Proposal: {p.proposal_id} - {p.state.value}"):
            st.markdown(f"**Research Question:** {p.research_question}")
            st.markdown(f"**Rationale:** {p.rationale}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Baseline Parameters**")
                st.json(p.baseline_parameters)
            with c2:
                st.write("**Proposed Parameters**")
                st.json(p.proposed_parameters)
                
            st.markdown("---")
            if p.state == EvolutionProposalState.REVIEW_REQUIRED:
                st.warning("STATUS: APPROVAL REQUIRED")
                if st.button("Approve for Research", key=f"approve_{p.proposal_id}"):
                    engine.approve_proposal(p.proposal_id)
                    st.rerun()
            elif p.state == EvolutionProposalState.APPROVED_FOR_RESEARCH:
                st.info("Approved. Ready for Sandbox.")
                if st.button("Run Experiment", key=f"run_{p.proposal_id}"):
                    engine.execute_proposal(p.proposal_id)
                    engine.validate_experiment(p.proposal_id)
                    st.rerun()
            elif p.state == EvolutionProposalState.VALIDATED:
                st.success(f"Final Research Answer: **{p.final_research_answer.value}**")
                st.write(f"Comparison ID: {p.comparison_id}")
