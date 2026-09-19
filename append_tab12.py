content = """
    with tabs[12]:
        st.subheader("CHAMPION VS CHALLENGER - PHASE 14")
        try:
            comparisons = pd.read_sql("SELECT * FROM champion_challenger ORDER BY timestamp DESC", conn)
            if comparisons.empty:
                st.write("No Champion-Challenger comparisons available. Run Phase 14 research script.")
            else:
                st.dataframe(comparisons[['id', 'timestamp', 'champion_id', 'challenger_id', 'decision']])
                
                selected_comp = st.selectbox("Select Comparison to Inspect", comparisons['id'].tolist(), key='champ_chall_id')
                comp_row = comparisons[comparisons['id'] == selected_comp].iloc[0]
                
                import json
                comp_json = json.loads(comp_row['comparison_json'])
                st.write(f"**Decision**: {comp_json.get('decision')}")
                st.write(f"**Reasons**: {', '.join(comp_json.get('decision_reasons', []))}")
                
                st.write("### Scorecard")
                st.json(comp_json.get('scorecard', {}))
        except Exception as e:
             st.write("Database table 'champion_challenger' not found or empty.")
"""
with open('app/dashboard/app.py', 'a') as f:
    f.write(content)
