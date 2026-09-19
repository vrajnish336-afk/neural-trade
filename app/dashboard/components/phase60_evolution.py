import streamlit as st
import pandas as pd
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.learning.paper_evolution_engine import EvolutionProposalEngine
from app.learning.paper_evolution_models import ProposalStatus

def render_phase60_evolution_tab(conn):
    st.markdown("## PHASE 60: PAPER EVOLUTION (HUMAN-IN-THE-LOOP)")
    st.warning("PAPER TRADING ONLY. LIVE TRADING DISABLED. Evolution proposals require EXPLICIT HUMAN APPROVAL before application.")

    repo = PaperEvolutionRepository()
    engine = EvolutionProposalEngine(repo)
    lessons = repo.get_lessons()
    proposals = repo.get_proposals()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Lessons", len(lessons))
    c2.metric("Validated Lessons", sum(1 for l in lessons if l.confidence_status == "VALIDATED"))
    c3.metric("Pending Proposals", sum(1 for p in proposals if p.status == ProposalStatus.REVIEW_REQUIRED))

    st.markdown("### LESSONS BANK (FROM CLOSED PAPER TRADES)")
    if not lessons:
        st.info("No lessons extracted yet.")
    else:
        lesson_data = []
        for l in lessons:
            lesson_data.append({
                "Lesson ID": l.lesson_id,
                "Strategy": l.strategy,
                "Regime": l.regime,
                "Observation": l.observation,
                "Sample Size": l.sample_count,
                "PnL": l.observed_pnl,
                "Status": l.confidence_status.value
            })
        st.dataframe(pd.DataFrame(lesson_data), use_container_width=True)

    st.markdown("### EVOLUTION PROPOSALS")
    if not proposals:
        st.info("No proposals generated yet.")
    else:
        for p in proposals:
            with st.expander(f"Proposal {p.proposal_id[:8]} - {p.affected_parameter} ({p.status.value})"):
                st.write(f"**Strategy:** {p.affected_strategy}")
                st.write(f"**Reason:** {p.reason}")
                st.write(f"**Evidence:** {p.evidence_summary} (Sample Size: {p.sample_size})")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Current Value", str(p.current_value))
                col2.metric("Proposed Value", str(p.proposed_value))
                col3.metric("Delta", str(p.delta))
                
                if p.status == ProposalStatus.REVIEW_REQUIRED:
                    st.warning("HUMAN APPROVAL REQUIRED")
                    c_app, c_rej = st.columns(2)
                    with c_app:
                        if st.button("APPROVE & APPLY", key=f"approve_{p.proposal_id}"):
                            p.status = ProposalStatus.APPROVED
                            repo.save_proposal(p)
                            if engine.apply_proposal(p.proposal_id):
                                st.success("Proposal applied successfully.")
                            else:
                                st.error("Failed to apply proposal.")
                            st.rerun()
                    with c_rej:
                        if st.button("REJECT", key=f"reject_{p.proposal_id}"):
                            p.status = ProposalStatus.REJECTED
                            repo.save_proposal(p)
                            st.rerun()
                elif p.status == ProposalStatus.APPLIED:
                    st.success("This proposal is active.")
                    if st.button("ROLLBACK", key=f"rollback_{p.proposal_id}"):
                        if engine.rollback_proposal(p.proposal_id):
                            st.success("Rolled back successfully.")
                        else:
                            st.error("Failed to rollback.")
                        st.rerun()
