import streamlit as st
import pandas as pd
from app.learning.repository import LearningRepository

def render_learning_tab(conn):
    st.markdown("## PHASE 23: LESSONS & EVOLUTION")
    st.warning("PAPER / RESEARCH ONLY. LIVE TRADING DISABLED. Evolution proposals do not automatically deploy.")

    repo = LearningRepository()
    lessons = repo.get_lessons()
    proposals = repo.get_proposals()

    st.markdown("### LESSONS BANK")
    if not lessons:
        st.info("No research lessons have been extracted yet.")
    else:
        # Compute ranks dynamically for display
        from app.learning.lesson_engine import LessonEngine
        engine = LessonEngine()
        ranked = engine.rank_lessons(lessons)
        
        lesson_data = []
        for l in ranked:
            lesson_data.append({
                "Lesson_ID": l.lesson_id,
                "Strategy": l.strategy,
                "Regime": l.regime,
                "Evidence Count": l.evidence_count,
                "Confidence": f"{l.confidence_score:.2f}",
                "Conflicts": len(l.conflicting_observation_ids),
                "Rank Score": f"{(l.evidence_count * l.confidence_score) - (len(l.conflicting_observation_ids) * 0.5):.2f}",
                "Status": l.state.value,
                "Lesson": l.lesson_statement,
                "Last Observed": l.last_observed_at.isoformat()
            })
        st.dataframe(pd.DataFrame(lesson_data), use_container_width=True)

    st.markdown("### EVOLUTION PROPOSALS")
    if not proposals:
        st.info("No evolution proposals have been generated yet.")
    else:
        prop_data = []
        for p in proposals:
            prop_data.append({
                "Proposal_ID": p.proposal_id,
                "Strategy": p.strategy,
                "Baseline": p.baseline_parameters_json,
                "Proposed Change": p.proposed_parameters_json,
                "Reason": p.reason,
                "Validation Status": p.state.value,
                "Validation Run ID": p.validation_run_id or "N/A"
            })
        st.dataframe(pd.DataFrame(prop_data), use_container_width=True)
