import streamlit as st
from datetime import datetime, timezone
from app.copilot.models import CopilotRequest
from app.copilot.agent import CopilotAgent

def render_copilot_tab(conn):
    st.markdown("## PHASE 26: AI COPILOT")
    st.warning("PAPER / RESEARCH ONLY. AI COPILOT CANNOT EXECUTE TRADES.")
    
    # Session state
    if "copilot_history" not in st.session_state:
        st.session_state.copilot_history = []
        
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### Ask a Question")
        question = st.text_area("Question about your research system", height=150)
        
        st.markdown("### Context Selection")
        use_world = st.checkbox("World Intelligence", value=True)
        use_lessons = st.checkbox("Lessons Bank", value=True)
        use_proposals = st.checkbox("Evolution Proposals", value=True)
        use_forecasts = st.checkbox("Forecasts", value=True)
        
        symbol = st.text_input("Filter by Symbol (Optional)", "")
        
        # We just use datetime.utcnow() for ease in UI, but could add date picker
        as_of = datetime.utcnow().replace(tzinfo=timezone.utc)
        
        if st.button("Ask Copilot"):
            if not question.strip():
                st.error("Please enter a question.")
            else:
                scope = []
                if use_world: scope.append("world_intelligence")
                if use_lessons: scope.append("lessons")
                if use_proposals: scope.append("evolution_proposals")
                if use_forecasts: scope.append("forecasts")
                
                req = CopilotRequest(
                    question=question,
                    as_of=as_of,
                    context_scope=scope,
                    symbol=symbol if symbol else None
                )
                
                with st.spinner("AI is analyzing research context..."):
                    agent = CopilotAgent()
                    resp = agent.ask(req)
                    
                st.session_state.copilot_history.insert(0, {
                    "question": question,
                    "answer": resp.answer,
                    "is_fallback": resp.is_fallback,
                    "sources": resp.evidence_references,
                    "as_of": resp.as_of
                })
                
    with col2:
        st.markdown("### Response")
        if not st.session_state.copilot_history:
            st.info("Ask a question to see the response.")
        else:
            latest = st.session_state.copilot_history[0]
            
            if latest["is_fallback"]:
                st.error("AI Service Unavailable. Returning deterministic raw context:")
            
            st.markdown(latest["answer"])
            st.markdown("---")
            st.caption(f"**As Of:** {latest['as_of'].isoformat()} | **Sources Checked:** {', '.join(latest['sources'])}")
            
            if len(st.session_state.copilot_history) > 1:
                with st.expander("Previous Conversations"):
                    for i, past in enumerate(st.session_state.copilot_history[1:]):
                        st.markdown(f"**Q:** {past['question']}")
                        st.markdown(f"**A:** {past['answer']}")
                        st.markdown("---")
