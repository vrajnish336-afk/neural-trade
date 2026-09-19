import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from app.intelligence.service import WorldIntelligenceService
from app.intelligence.repository import IntelligenceRepository

def render_intelligence_tab(conn):
    st.markdown("## PHASE 25: WORLD INTELLIGENCE")
    st.warning("PAPER / RESEARCH ONLY. WORLD INTELLIGENCE IS CONTEXT, NOT A TRADING SIGNAL.")
    
    svc = WorldIntelligenceService()
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("### Control")
        if st.button("Fetch Latest World Data"):
            with st.spinner("Fetching..."):
                svc.fetch_and_store_all()
            st.success("Fetched.")
            
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    ctx = svc.aggregate_context(as_of=now)
    
    st.markdown("### Market Sentiment")
    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        st.metric("Sentiment Summary", f"{ctx.sentiment_summary:.2f}" if ctx.sentiment_summary is not None else "UNKNOWN")
    with mcol2:
        st.metric("Source Count", ctx.source_count)
    with mcol3:
        st.metric("High Quality Sources", ctx.high_quality_source_count)
        
    st.markdown("### Fear & Greed")
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        st.metric("Value (Normalized)", f"{ctx.fear_and_greed_value:.2f}" if ctx.fear_and_greed_value is not None else "NOT_AVAILABLE")
    with fcol2:
        st.metric("Status", ctx.fear_and_greed_classification or "NOT_AVAILABLE")
        
    st.markdown("### Macro Context")
    st.info(f"Macro Status: {ctx.macro_summary}")
    st.info(f"Flow Status: {ctx.flow_summary}")
    
    st.markdown("### Recent News Observations")
    repo = IntelligenceRepository()
    obs = repo.get_observations(as_of=now, source_type="NEWS", limit=20)
    
    if obs:
        df = pd.DataFrame([{
            "Publisher": o.publisher,
            "Quality": o.source_quality.value,
            "Published": o.published_at.isoformat() if o.published_at else "UNKNOWN",
            "Retrieved": o.retrieved_at.isoformat(),
            "Relevance": o.symbol_relevance
        } for o in obs])
        st.dataframe(df, use_container_width=True)
    else:
        st.write("No news observations available.")
