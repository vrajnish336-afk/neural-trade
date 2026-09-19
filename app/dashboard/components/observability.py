import streamlit as st
import pandas as pd
import sqlite3
from app.services.observability import ObservabilityService

def render_observability_tab(analytics_runs: pd.DataFrame, conn: sqlite3.Connection):
    st.markdown("### OBSERVABILITY & EXPERIMENT ANALYSIS")
    
    if analytics_runs.empty:
        st.write("No analytics runs available.")
        return
        
    run_id = st.selectbox("Select Analytics Run to Observe", analytics_runs['id'].tolist(), key="obs_run")
    if not run_id:
        return
        
    report = ObservabilityService.get_analytics_report(run_id)
    if not report:
        st.error("Failed to load FullAnalyticsReport for this run.")
        return
        
    st.write(f"**Run ID:** {report.backtest_id}")
    
    st.markdown("#### Execution Friction")
    st.text(ObservabilityService.format_friction(report))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Telemetry Funnel")
        st.text(ObservabilityService.format_funnel(report))
        
    with col2:
        st.markdown("#### Regime Attribution")
        st.text(ObservabilityService.format_regimes(report))
        
    st.markdown("---")
    st.markdown("### EVIDENCE EVALUATION")
    # Observability uses analytics_runs (report). But we need ResearchExperiment to evaluate.
    # Try fetching the experiment using the report's backtest_id
    experiment = ObservabilityService.get_experiment(report.backtest_id)
    if not experiment:
        st.warning("Evidence Evaluation requires a full ResearchExperiment record. (Legacy backtest-only run)")
    else:
        from app.dashboard.components.lineage import render_lineage_component
        render_lineage_component(experiment)
        
        from app.research.evidence import ResearchEvidenceEvaluator
        evaluator = ResearchEvidenceEvaluator()
        summary = evaluator.evaluate(experiment)
        
        st.write(f"**Conclusion:** {summary.conclusion.value}")
        st.write(f"**Status:** {summary.status.value}")
        st.write(f"**Consistency:** {'✅ Valid' if summary.consistency.is_consistent else '❌ Inconsistent'}")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### Data Coverage")
            st.write(f"Train: {summary.data_coverage.train}")
            st.write(f"Validation: {summary.data_coverage.validation}")
            st.write(f"OOS: {summary.data_coverage.oos}")
        with c2:
            st.markdown("#### Robustness")
            st.write(f"Walk-forward: {summary.robustness.walk_forward.value}")
            st.write(f"Multi-seed: {summary.robustness.multi_seed.value}")
            st.write(f"Cost/Slippage Stress: {summary.robustness.cost_slippage_stress.value}")
        with c3:
            st.markdown("#### Sample Size")
            st.write(f"OOS trades: {summary.sample_size_eval.oos_trades} / {summary.sample_size_eval.standard}")
            st.write(f"Assessment: {summary.sample_size_eval.assessment}")
            
        st.markdown("#### Reasons")
        for r in summary.reasons:
            st.markdown(f"- {r}")
            
        st.markdown("#### Limitations")
        for l in summary.limitations:
            st.markdown(f"- {l}")
        st.caption(f"* {summary.statistical_significance_note}")

        st.markdown("---")
        st.markdown("### COMPARE EXPERIMENTS")
        exp_list = analytics_runs['id'].tolist()
        compare_id = st.selectbox("Select another experiment to compare with", ["-- Select --"] + exp_list, key="compare_run")
        if compare_id and compare_id != "-- Select --":
            compare_exp = ObservabilityService.get_experiment(compare_id)
            if compare_exp:
                from app.research.comparator import CrossExperimentComparator
                comparator = CrossExperimentComparator()
                comp_report = comparator.compare(experiment, compare_exp)
                
                st.write(f"**Comparability:** {comp_report.comparability.value}")
                
                st.markdown("#### Differences")
                if not comp_report.differences:
                    st.write("None (Identical core conditions)")
                else:
                    for diff in comp_report.differences:
                        st.markdown(f"- {diff}")
                        
                st.markdown("#### Conclusion")
                st.write(comp_report.conclusion)
                
                c_a, c_b = st.columns(2)
                with c_a:
                    st.markdown(f"**Run A (Current)**")
                    st.write(f"OOS Trades: {comp_report.oos_trades_1}")
                    st.write(f"OOS PnL: {comp_report.oos_pnl_1}")
                    st.write(f"OOS PF: {comp_report.oos_pf_1}")
                with c_b:
                    st.markdown(f"**Run B (Compared)**")
                    st.write(f"OOS Trades: {comp_report.oos_trades_2}")
                    st.write(f"OOS PnL: {comp_report.oos_pnl_2}")
                    st.write(f"OOS PF: {comp_report.oos_pf_2}")
            else:
                st.warning("Selected comparison run lacks a full ResearchExperiment record.")
