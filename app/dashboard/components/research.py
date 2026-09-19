import streamlit as st
import pandas as pd
import sqlite3
import json
import os

def render_research_tab(
    backtests: pd.DataFrame, 
    analytics_runs: pd.DataFrame, 
    research_experiments: pd.DataFrame, 
    conn: sqlite3.Connection
):
    st.markdown("### RESEARCH & VALIDATION")
    
    st.warning("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
    
    tabs = st.tabs([
        "Overview & Trades",
        "Analytics Reports",
        "Failures & Attribution",
        "RESEARCH LAB",
        "Robustness Lab",
        "Failure Diagnostics",
        "Portfolio Risk",
        "Research Governance",
        "Champion vs Challenger",
        "AI Research & Intelligence",
        "Paper Monitoring Cycle",
        "Research Candidate Portfolio"
    ])
    
    with tabs[0]:
        st.subheader("Recent Backtests")
        st.dataframe(backtests)
        
        st.subheader("Trade Details")
        if not backtests.empty:
            bt_id = st.selectbox("Select Backtest for Trades", backtests['id'].tolist(), key="trade_bt")
            try:
                trades = pd.read_sql(f"SELECT * FROM trades WHERE backtest_id = '{bt_id}'", conn)
                if not trades.empty:
                    st.dataframe(trades)
            except Exception as e:
                st.error(f"Error loading trades: {e}")
                
    with tabs[1]:
        st.subheader("Analytics Reports")
        if not analytics_runs.empty:
            selected_analytics = st.selectbox("Select Analytics Run", analytics_runs['id'].tolist())
            if selected_analytics:
                report_row = analytics_runs[analytics_runs['id'] == selected_analytics].iloc[0]
                report_json = json.loads(report_row['report_json'])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Win Rate", f"{report_json['trade_metrics']['win_rate']:.2f}%")
                c2.metric("Profit Factor", f"{report_json['trade_metrics']['profit_factor']:.2f}")
                c3.metric("Max Drawdown", f"{report_json['equity_metrics']['max_drawdown_pct']:.2f}%")
                c4.metric("Avg Trade PNL", f"${report_json['trade_metrics']['average_pnl']:.2f}")
                
                st.write("### Strategy Attribution")
                st.table(pd.DataFrame(report_json['strategy_attribution']))
                
                st.write("### Signal Bucket Attribution")
                st.table(pd.DataFrame(report_json['signal_bucket_attribution']))
        else:
            st.write("No analytics generated yet.")
            
    with tabs[2]:
        st.subheader("Failure Analysis & Intelligence")
        if not analytics_runs.empty:
            a_id = st.selectbox("Select Analytics Run for Failures", analytics_runs['id'].tolist(), key="fail_run")
            if a_id:
                report_row = analytics_runs[analytics_runs['id'] == a_id].iloc[0]
                report_json = json.loads(report_row['report_json'])
                
                st.write("### Intelligence Breakdown")
                st.table(pd.DataFrame(report_json['intelligence_attribution']))
                
                st.write("### Identified Failure Patterns")
                for f in report_json['failure_findings']:
                    st.warning(f"**Pattern Found (n={f['sample_size']})**: {f['finding']}")
        else:
            st.write("No analytics runs available.")

    with tabs[3]:
        st.subheader("Research Lab & Out-of-Sample Validation")
        if not research_experiments.empty:
            exp_id = st.selectbox("Select Research Experiment", research_experiments['id'].tolist(), key="res_exp")
            if exp_id:
                exp_row = research_experiments[research_experiments['id'] == exp_id].iloc[0]
                exp_json = json.loads(exp_row['experiment_json'])
                
                st.write("### Experiment Metadata")
                st.write(f"**Symbols:** {', '.join(exp_json['symbols'])}")
                st.write(f"**Seed:** {exp_json['random_seed']}")
                
                st.write("### Out-of-Sample Results")
                oos = exp_json.get('out_of_sample_report')
                if oos:
                    tm = oos['trade_metrics']
                    em = oos['equity_metrics']
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("OOS Trades", tm['total_trades'])
                    c2.metric("OOS Return", f"{em['total_return_pct']:.2f}%")
                    c3.metric("OOS Win Rate", f"{tm['win_rate']:.2f}%")
                    c4.metric("OOS Max Drawdown", f"{em['max_drawdown_pct']:.2f}%")
                    
                    from app.research.models import get_sample_size_warning
                    warning = get_sample_size_warning(tm['total_trades'])
                    if warning != "LARGER_SAMPLE":
                        st.warning(f"**Sample Size Warning**: {warning}. This data may be statistically insignificant.")
                else:
                    st.write("N/A - Insufficient Data")
                    
                st.write("### Stress Testing & Robustness")
                st_res = exp_json.get('stress_test_results', [])
                if st_res:
                    st.table(pd.DataFrame(st_res))
                else:
                    st.write("No stress tests available.")
        else:
            st.write("No research experiments found. Run `python run_research_experiment.py`")

    with tabs[4]:
        st.subheader("Robustness Lab (Phase 10)")
        rob_path = "reports/phase10_robustness.json"
        if os.path.exists(rob_path):
            with open(rob_path, "r") as f:
                r_data = json.load(f)
                
            sc = r_data.get("scorecard", {})
            st.write("### Robustness Scorecard")
            col1, col2, col3 = st.columns(3)
            col1.metric("Overall Status", sc.get("overall_status", ""))
            col2.metric("Cross-Seed Stability", sc.get("cross_seed_stability", ""))
            col3.metric("Sample Size", sc.get("sample_size_adequacy", ""))
            
            st.write("### Monte Carlo Stability")
            mc = r_data.get("monte_carlo", {})
            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Median Return", f"{mc.get('median_return_pct', 0):.2f}%")
            mcol2.metric("5th %ile Return", f"{mc.get('p05_return_pct', 0):.2f}%")
            mcol3.metric("95th %ile Return", f"{mc.get('p95_return_pct', 0):.2f}%")
            
            st.write("### Market Regime Segregation")
            regimes = r_data.get("regimes", {})
            reg_df = pd.DataFrame.from_dict(regimes, orient="index")
            st.table(reg_df)
            
            st.write("### Cross-Seed Validation")
            seeds = r_data.get("seed_robustness", [])
            if seeds:
                seed_df = pd.DataFrame(seeds)
                st.table(seed_df)
        else:
            st.write("No robustness data found. Run `python run_robustness_audit.py`")

    with tabs[5]:
        st.subheader("Failure Diagnostics (Phase 11)")
        diag_path = "reports/phase11_diagnostics.json"
        if os.path.exists(diag_path):
            with open(diag_path, "r") as f:
                diag_data = json.load(f)
                
            st.write("### Regime Failure Matrix")
            rm = diag_data.get("regime_matrix", [])
            if rm:
                st.dataframe(pd.DataFrame(rm))
                
            st.write("### Signal Score Analysis")
            sa = diag_data.get("score_analysis", [])
            if sa:
                st.table(pd.DataFrame(sa))
                
            st.write("### TRENDING_UP Diagnostics")
            st.json(diag_data.get("trending_up_diagnostics", {}))
            
            st.write("### Rejection Funnel by Regime")
            st.json(diag_data.get("rejection_funnel", {}))
        else:
            st.write("No failure diagnostics found. Run `python run_failure_diagnostics.py`")

    with tabs[6]:
        st.subheader("PORTFOLIO RISK & EXECUTION - PHASE 12")
        pr_path = "reports/phase12_portfolio_risk.json"
        if os.path.exists(pr_path):
            with open(pr_path, "r") as f:
                pr_data = json.load(f)
                
            st.write("### Multi-Symbol Portfolio Exposure")
            exposure = pr_data.get("portfolio_exposure", {})
            c1, c2, c3 = st.columns(3)
            c1.metric("Max Concurrent Positions", exposure.get("max_concurrent_positions", 0))
            c2.metric("Peak Gross Exposure", f"${exposure.get('peak_gross_exposure', 0):.2f}")
            c3.metric("Peak Net Exposure", f"${exposure.get('peak_net_exposure', 0):.2f}")
            
            st.write("### Correlation Analysis")
            corr = pr_data.get("correlation", {})
            st.write(f"Highly correlated pairs found: {corr.get('highly_correlated_pairs', 0)}")
            if corr.get('matrix'):
                st.dataframe(pd.DataFrame(corr['matrix']))
                
            st.write("### Execution Stress Matrix")
            exec_stress = pr_data.get("execution_stress", [])
            if exec_stress:
                st.table(pd.DataFrame(exec_stress))
                
            st.write("### Adversarial Scenarios")
            adv = pr_data.get("adversarial_scenarios", [])
            if adv:
                st.table(pd.DataFrame(adv))
                
            st.write("### Extended Drawdown Analysis")
            dd = pr_data.get("drawdown_analysis", {})
            col1, col2, col3 = st.columns(3)
            col1.metric("Max Drawdown", f"{dd.get('max_drawdown_pct', 0):.2f}%")
            col2.metric("Longest Drawdown (Periods)", dd.get('longest_drawdown_periods', 0))
            col3.metric("Max Recovery Time", dd.get('max_recovery_periods', 0))
            
            st.write("### Historical Sequence Risk Stress")
            seq = pr_data.get("sequence_stress", {})
            st.write(f"Simulations: {seq.get('simulations', 0)}")
            if seq.get("thresholds"):
                st.table(pd.DataFrame(seq["thresholds"]).T)
        else:
            st.write("No Portfolio Risk data found. Run phase 12 research script.")

    with tabs[7]:
        st.subheader("RESEARCH GOVERNANCE - PHASE 13")
        if research_experiments.empty:
            st.write("No experiment data available. Run Phase 13 research script.")
        else:
            st.dataframe(research_experiments[['id', 'timestamp']])
            selected_exp_id = st.selectbox("Select Experiment to Inspect", research_experiments['id'].tolist(), key='gov_exp_id')
            exp_row = research_experiments[research_experiments['id'] == selected_exp_id].iloc[0]
            try:
                exp_json = json.loads(exp_row['experiment_json'])
                st.write(f"**Experiment Name**: {exp_json.get('experiment_name', 'Unnamed')}")
                st.write(f"**Status**: {exp_json.get('status')}")
                st.write(f"**Classification**: {exp_json.get('classification', 'MIXED_EVIDENCE')}")
                st.write(f"**Dataset Hash**: {exp_json.get('dataset_id')}")
                
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Configuration Snapshot**")
                    st.json(exp_json.get('configuration_snapshot', {}))
                with c2:
                    st.write("**Dataset Identity**")
                    st.json(exp_json.get('dataset_identity', {}))
                    st.write("**Seeds**")
                    st.json(exp_json.get('seeds', {}))
            except Exception as e:
                st.error(f"Error parsing experiment JSON: {e}")

    with tabs[8]:
        st.subheader("CHAMPION VS CHALLENGER - PHASE 14")
        try:
            comparisons = pd.read_sql("SELECT * FROM champion_challenger ORDER BY timestamp DESC", conn)
            if comparisons.empty:
                st.write("No Champion-Challenger comparisons available. Run Phase 14 research script.")
            else:
                st.dataframe(comparisons[['id', 'timestamp', 'champion_id', 'challenger_id', 'decision']])
                
                selected_comp = st.selectbox("Select Comparison to Inspect", comparisons['id'].tolist(), key='champ_chall_id')
                comp_row = comparisons[comparisons['id'] == selected_comp].iloc[0]
                
                comp_json = json.loads(comp_row['comparison_json'])
                st.write(f"**Decision**: {comp_json.get('decision')}")
                st.write(f"**Reasons**: {', '.join(comp_json.get('decision_reasons', []))}")
                
                st.write("### Scorecard")
                st.json(comp_json.get('scorecard', {}))
        except Exception as e:
             st.write("Database table 'champion_challenger' not found or empty.")

    with tabs[9]:
        st.subheader("AI RESEARCH & INTELLIGENCE - PHASE 12")
        st.warning("PAPER / RESEARCH ONLY. AI Predictions are not guaranteed and must be verified.")
        try:
            ai_data = pd.read_sql("""
                SELECT 
                    a.analysis_timestamp as Analysed_At,
                    n.title as Article_Title,
                    a.evidence_type as Evidence_Type,
                    a.relevance_score as Relevance,
                    a.confidence as Confidence,
                    a.research_hypothesis as Hypothesis,
                    a.provider as Provider,
                    a.is_fallback as Fallback,
                    a.error_message as Error
                FROM ai_research_analysis a
                JOIN news_articles n ON a.article_id = n.id
                ORDER BY a.analysis_timestamp DESC
                LIMIT 100
            """, conn)
            
            if ai_data.empty:
                st.write("No AI analysis data found. Run `python cli.py research-news`")
            else:
                st.dataframe(ai_data, use_container_width=True)
                
                st.write("### Latest Hypotheses")
                hypo_data = ai_data[ai_data['Hypothesis'].notna() & (ai_data['Hypothesis'] != '')]
                for _, row in hypo_data.head(5).iterrows():
                    st.info(f"**[{row['Evidence_Type']}] {row['Article_Title']}**\n\n*Hypothesis*: {row['Hypothesis']}")
                    
        except Exception as e:
            st.write(f"Could not load AI Research data: {e}")
            
        st.write("### LONG-TERM PAPER TRACK RECORDS (Phase 19)")
        try:
            track_data = pd.read_sql("""
                SELECT 
                    track_record_id as ID,
                    identity_hash as Identity,
                    current_health_state as Health,
                    initial_equity as Start_Eq,
                    current_equity as Current_Eq,
                    cumulative_return_pct as Return_Pct,
                    max_drawdown_pct as Max_DD,
                    observation_count as Obs_Count
                FROM paper_track_records
                ORDER BY updated_at DESC
                LIMIT 50
            """, conn)
            if track_data.empty:
                st.write("No long-term track records found.")
            else:
                st.dataframe(track_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load Paper Track Records: {e}")
            
        st.write("### FORWARD PAPER VALIDATION (Phase 18)")
        try:
            fwd_data = pd.read_sql("""
                SELECT 
                    validation_id as ID,
                    identity_hash as Identity,
                    state as State,
                    drift_state as Drift,
                    forward_start as Start_Date,
                    forward_end as End_Date,
                    created_at as Created_At
                FROM forward_validation_runs
                ORDER BY created_at DESC
                LIMIT 50
            """, conn)
            if fwd_data.empty:
                st.write("No forward validation runs found.")
            else:
                st.dataframe(fwd_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load Forward Validations: {e}")
            
        st.write("### AI RESEARCH KNOWLEDGE & GAPS (Phase 17)")
        try:
            gaps_data = pd.read_sql("""
                SELECT 
                    gap_id,
                    identity_hash as Identity,
                    gap_type as Gap_Type,
                    severity as Severity,
                    recommended_action as Action,
                    created_at as Created_At
                FROM research_evidence_gaps
                WHERE status = 'OPEN'
                ORDER BY created_at DESC
                LIMIT 50
            """, conn)
            if gaps_data.empty:
                st.write("No open evidence gaps found.")
            else:
                st.write("#### 🔍 Open Evidence Gaps")
                st.dataframe(gaps_data, use_container_width=True)
                
            changes_data = pd.read_sql("""
                SELECT 
                    identity_hash as Identity,
                    change_type as Type,
                    previous_decision as Prev_Decision,
                    new_decision as New_Decision,
                    reason as Reason,
                    created_at as Created_At
                FROM research_knowledge_changes
                ORDER BY created_at DESC
                LIMIT 20
            """, conn)
            if not changes_data.empty:
                st.write("#### 📜 Recent Knowledge Changes")
                st.dataframe(changes_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load Research Knowledge: {e}")
            
        st.write("### AI RESEARCH CONCLUSIONS & DECISIONS (Phase 16)")
        try:
            conc_data = pd.read_sql("""
                SELECT 
                    conclusion_id as Conclusion_ID,
                    identity_hash as Identity,
                    decision_state as Decision,
                    confidence_state as Confidence,
                    summary as Summary,
                    next_research_action as Next_Action,
                    created_at as Created_At
                FROM research_conclusions
                ORDER BY created_at DESC
                LIMIT 50
            """, conn)
            if conc_data.empty:
                st.write("No Research Conclusions found.")
            else:
                st.dataframe(conc_data, use_container_width=True)
                
            conflicts_data = pd.read_sql("""
                SELECT conflict_id, conflict_type, severity, explanation, resolution_status
                FROM research_conflicts
                WHERE resolution_status = 'UNRESOLVED'
            """, conn)
            if not conflicts_data.empty:
                st.write("#### ⚠️ Unresolved Research Conflicts")
                st.dataframe(conflicts_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load Research Conclusions: {e}")
            
        st.write("### AI RESEARCH JOBS (Phase 15)")
        try:
            jobs_data = pd.read_sql("""
                SELECT 
                    job_id as Job_ID,
                    state as State,
                    round(priority, 2) as Priority,
                    retry_count as Retries,
                    failure_reason as Failure_Reason,
                    created_at as Created_At
                FROM research_jobs
                ORDER BY created_at DESC
                LIMIT 50
            """, conn)
            if jobs_data.empty:
                st.write("No Research Jobs found.")
            else:
                st.dataframe(jobs_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load Research Jobs: {e}")
            
        st.write("### AI RESEARCH OPPORTUNITIES (Phase 14)")
        try:
            opp_data = pd.read_sql("""
                SELECT 
                    opportunity_id as ID,
                    hypothesis_text as Hypothesis,
                    affected_symbols as Symbols,
                    mapped_strategy as Strategy,
                    round(research_priority, 2) as Priority,
                    status as Status,
                    reason as Reason
                FROM research_opportunities
                ORDER BY research_priority DESC
                LIMIT 50
            """, conn)
            if opp_data.empty:
                st.write("No Opportunities found.")
            else:
                st.dataframe(opp_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load Opportunities: {e}")
            
        st.write("### AI RESEARCH MEMORY (Phase 14)")
        try:
            mem_data = pd.read_sql("""
                SELECT 
                    identity_hash as Identity,
                    canonical_hypothesis as Hypothesis,
                    affected_symbols as Symbols,
                    mapped_strategy as Strategy,
                    latest_conclusion as Latest_Conclusion
                FROM research_memory
                ORDER BY last_researched_at DESC
                LIMIT 50
            """, conn)
            if mem_data.empty:
                st.write("No Memory records found.")
            else:
                st.dataframe(mem_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load Memory: {e}")
            
        st.write("### AI RESEARCH LOOP (Phase 13)")
        try:
            loop_data = pd.read_sql("""
                SELECT 
                    r.request_id as Request_ID,
                    a.title as Article_Title,
                    r.hypothesis_text as Hypothesis,
                    r.affected_symbols as Symbols,
                    r.mapped_strategy as Strategy,
                    r.status as Status,
                    r.evidence_conclusion as Conclusion,
                    r.failure_reason as Failure_Reason
                FROM ai_research_requests r
                LEFT JOIN ai_research_analysis an ON r.analysis_id = an.analysis_id
                LEFT JOIN news_articles a ON an.article_id = a.id
                ORDER BY r.created_at DESC
                LIMIT 50
            """, conn)
            
            if loop_data.empty:
                st.write("No AI Research Loop requests found. Run `python cli.py research-loop`")
            else:
                st.dataframe(loop_data, use_container_width=True)
        except Exception as e:
            st.write(f"Could not load AI Research Loop data: {e}")
            
    with tabs[10]:
        st.subheader("PAPER MONITORING CYCLE (Phase 20)")
        st.warning("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED.")
        try:
            cycles_data = pd.read_sql("""
                SELECT 
                    cycle_id as Cycle_ID,
                    status as Status,
                    validations_discovered as Validations_Discovered,
                    observations_recorded as Observations_Recorded,
                    duplicates_skipped as Duplicates_Skipped,
                    health_transitions as Health_Transitions,
                    opportunities_created as Opportunities_Created,
                    knowledge_updates as Knowledge_Updates,
                    errors as Errors,
                    start_time as Start_Time,
                    end_time as End_Time
                FROM paper_monitoring_cycles
                ORDER BY start_time DESC
                LIMIT 50
            """, conn)
            
            if cycles_data.empty:
                st.write("No Paper Monitoring Cycles found. Run `python cli.py paper-monitor`")
            else:
                latest = cycles_data.iloc[0]
                st.write("### Latest Cycle Summary")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Status", latest['Status'])
                c2.metric("Observations Recorded", latest['Observations_Recorded'])
                c3.metric("Health Transitions", latest['Health_Transitions'])
                c4.metric("Errors", latest['Errors'])
                
                st.write("### Cycle History")
                st.dataframe(cycles_data, use_container_width=True)
                
        except Exception as e:
            st.write(f"Could not load Paper Monitoring Cycles data: {e}")
            
    with tabs[11]:
        st.subheader("RESEARCH CANDIDATE PORTFOLIO (Phase 21)")
        st.warning("PAPER / RESEARCH ONLY. NOT TRADING RECOMMENDATIONS.")
        
        try:
            from app.research.portfolio_service import ResearchPortfolioService
            port_svc = ResearchPortfolioService()
            portfolio = port_svc.get_portfolio(limit=50)
            
            if not portfolio:
                st.write("No candidates available.")
            else:
                port_data = []
                for c in portfolio:
                    port_data.append({
                        "Identity": c.identity_hash,
                        "Strategy": c.strategy,
                        "Priority": c.priority.value,
                        "Score": c.evidence_score.total_score,
                        "Decision": c.decision_state.value,
                        "Health": c.current_health.value,
                        "Fwd Obs": c.forward_observation_count,
                        "Fwd PnL": f"${c.cumulative_forward_pnl:.2f}",
                        "Fwd DD": f"{c.max_forward_drawdown_pct:.2f}%",
                        "Conflicts": c.unresolved_conflicts
                    })
                
                st.dataframe(pd.DataFrame(port_data), use_container_width=True)
                
                st.write("### Compare Candidates")
                selected_hashes = st.multiselect("Select candidates to compare (min 2)", [c.identity_hash for c in portfolio])
                if len(selected_hashes) >= 2:
                    if st.button("Compare"):
                        matrix = port_svc.compare_candidates(selected_hashes)
                        st.info(f"**Comparability:** {matrix.comparability.value}\n\n**Conclusion:** {matrix.conclusion}")
                        
                        if matrix.differences:
                            st.write("#### Differences:")
                            for d in matrix.differences:
                                st.write(f"- {d}")
                        
                        st.write("#### Candidate Ranking by Evidence:")
                        for idx, mc in enumerate(matrix.candidates):
                            with st.expander(f"{idx+1}. {mc.identity_hash} - Score: {mc.evidence_score.total_score} - Priority: {mc.priority.value}"):
                                st.write(f"**Health:** {mc.current_health.value}")
                                st.write(f"**Forward Observations:** {mc.forward_observation_count}")
                                st.write(f"**Unresolved Conflicts:** {mc.unresolved_conflicts}")
                                st.write("**Priority Reasons:**")
                                for r in mc.priority_reasons:
                                    st.write(f"- {r}")
                                    
                st.markdown("---")
                st.write("### LONGITUDINAL CANDIDATE HISTORY (Phase 22)")
                st.write("Analyze how evidence and state evolved over chronological time.")
                
                selected_history_hash = st.selectbox("Select Candidate for History", [""] + [c.identity_hash for c in portfolio])
                
                as_of_date = st.date_input("As-Of Barrier Date (Optional)", value=None)
                as_of_time = st.time_input("As-Of Barrier Time", value=None) if as_of_date else None
                
                if selected_history_hash:
                    if st.button("Load History"):
                        from app.research.longitudinal_service import LongitudinalCandidateTracker
                        from datetime import datetime
                        
                        tracker = LongitudinalCandidateTracker()
                        as_of_dt = None
                        if as_of_date:
                            # Combine date and time if available
                            if as_of_time:
                                as_of_dt = datetime.combine(as_of_date, as_of_time)
                            else:
                                as_of_dt = datetime.combine(as_of_date, datetime.min.time())
                                
                            st.warning(f"**AS-OF HISTORICAL VIEW ENABLED:** Simulating evidence state as of {as_of_dt.isoformat()}. Future evidence is hidden.")
                            
                        timeline = tracker.get_history(selected_history_hash, as_of=as_of_dt)
                        
                        if not timeline.events:
                            st.info("No historical events recorded for this candidate.")
                        else:
                            st.write(f"**Total Forward Observations:** {timeline.total_forward_observations}")
                            st.write(f"**Health Transitions:** {timeline.health_transitions_count}")
                            st.write(f"**Priority Transitions:** {timeline.priority_transitions_count}")
                            
                            st.write("#### Event Timeline")
                            for evt in timeline.events:
                                with st.expander(f"{evt.timestamp.isoformat()} - {evt.event_type.value}"):
                                    if not evt.transitions:
                                        st.write("*(No major state transitions triggered by this event)*")
                                    for t in evt.transitions:
                                        st.write(f"**{t.field_name.upper()}**: `{t.previous_state}` ➔ `{t.new_state}`")
                                        st.caption(f"Reason: {t.reason}")
                                        
                            if timeline.latest_snapshot:
                                st.success(f"Final Computed Priority (As-Of Barrier): **{timeline.latest_snapshot.priority.value}** (Score: {timeline.latest_snapshot.evidence_score.total_score})")

        except Exception as e:
            st.write(f"Could not load Portfolio data: {e}")

