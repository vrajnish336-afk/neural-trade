content = """
    with tabs[11]:
        st.subheader("RESEARCH GOVERNANCE - PHASE 13")
        if research_experiments.empty:
            st.write("No experiment data available. Run Phase 13 research script.")
        else:
            st.dataframe(research_experiments[['id', 'timestamp']])
            selected_exp_id = st.selectbox("Select Experiment to Inspect", research_experiments['id'].tolist(), key='gov_exp_id')
            exp_row = research_experiments[research_experiments['id'] == selected_exp_id].iloc[0]
            try:
                import json
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
"""
with open('app/dashboard/app.py', 'a') as f:
    f.write(content)
