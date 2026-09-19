import streamlit as st
from app.research.experiment_intelligence.service import ExperimentComparisonService
from app.sandbox.repository import SandboxRepository

def render_experiment_intelligence_tab(conn):
    st.markdown("## PHASE 28: EXPERIMENT INTELLIGENCE")
    st.warning("PAPER / RESEARCH ONLY. EXPERIMENT COMPARISON IS RESEARCH EVIDENCE ANALYSIS. NO AUTOMATIC STRATEGY DEPLOYMENT.")
    
    svc = ExperimentComparisonService()
    sb_repo = SandboxRepository()
    
    st.markdown("### Compare Experiments")
    
    col1, col2 = st.columns(2)
    
    exps = sb_repo._get_conn().execute("SELECT experiment_id FROM research_sandbox_experiments").fetchall()
    exp_ids = [e[0] for e in exps] if exps else []
    
    with col1:
        exp_a = st.selectbox("Experiment A", options=exp_ids, key="exp_a")
    with col2:
        exp_b = st.selectbox("Experiment B", options=exp_ids, key="exp_b")
        
    if st.button("Compare"):
        if not exp_a or not exp_b:
            st.error("Please select two experiments.")
            return
            
        comp = svc.compare_experiments(exp_a, exp_b)
        if not comp:
            st.error("Failed to compare.")
            return
            
        st.markdown(f"**Compatibility:** {comp.compatibility.value}")
        for n in comp.compatibility_notes:
            st.write(f"- {n}")
            
        st.markdown("### EVIDENCE PROFILE")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Experiment A ({exp_a})**")
            st.write(f"Return: {comp.profile_a.performance_return_pct:.2%}")
            st.write(f"Sample Size: {comp.profile_a.coverage_sample_size}")
            st.write(f"Overall Strength: {comp.profile_a.overall_strength.value}")
            
        with c2:
            st.markdown(f"**Experiment B ({exp_b})**")
            st.write(f"Return: {comp.profile_b.performance_return_pct:.2%}")
            st.write(f"Sample Size: {comp.profile_b.coverage_sample_size}")
            st.write(f"Overall Strength: {comp.profile_b.overall_strength.value}")
            
        st.markdown("---")
        st.markdown("### FINAL RESEARCH ASSESSMENT")
        st.markdown(f"**{comp.final_research_assessment.value}**")
        st.info(f"Reason: {comp.recommendation}")
        st.write("Limitations: This assessment relies on historical simulations and does not guarantee future live performance.")
