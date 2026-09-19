import streamlit as st
import pandas as pd
from app.research.planner.planner import ResearchDecisionPlanner

def render_planner_tab(conn):
    st.markdown("## PHASE 32: RESEARCH DECISION CENTER")
    st.warning("PAPER / RESEARCH ONLY. RESEARCH PRIORITY IS NOT PROFITABILITY. NO TRADE EXECUTION CONTROLS. HUMAN APPROVAL REQUIRED.")
    
    planner = ResearchDecisionPlanner()
    
    if st.button("Generate / Update Research Plan"):
        with st.spinner("Analyzing Evidence Graph for gaps & conflicts..."):
            planner.generate_plan()
            st.success("Plan updated.")
            
    st.markdown("---")
    
    st.markdown("### Top Research Questions")
    
    decisions = planner.repo.get_ranked_decisions()
    
    if decisions:
        for d in decisions:
            with st.expander(f"[{d.status.value}] Priority: {d.priority:.2f} | Question ID: {d.research_question_id[:8]}..."):
                c = planner.repo.get_candidate(d.research_question_id)
                st.write(f"**Question:** {c.research_question if c else 'Unknown'}")
                st.write(f"**Action:** {d.recommended_action.value}")
                st.write(f"**Feasibility:** {d.feasibility}")
                st.write(f"**Expected Information Value:** {d.expected_information_value:.2f}")
                
                st.markdown("**Priority Breakdown:**")
                st.json(d.priority_breakdown.model_dump())
                
                st.markdown("**Rationale:**")
                st.info(d.rationale)
                
                if d.status.value == "REVIEW_REQUIRED":
                    st.warning("Needs explicit approval to enter Continuous Research Cycle.")
                    if st.button("REVIEW FOR RESEARCH / APPROVE", key=f"approve_{d.decision_id}"):
                        planner.approve_decision(d.decision_id)
                        st.rerun()
    else:
        st.info("No research decisions available.")
