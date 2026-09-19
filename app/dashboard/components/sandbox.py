import streamlit as st
import json
from app.sandbox.service import SandboxService
from app.sandbox.models import ProposalStatus

def render_sandbox_tab(conn):
    st.markdown("## PHASE 27: AI RESEARCH SANDBOX")
    st.warning("PAPER / RESEARCH ONLY. AI-GENERATED CODE IS RESEARCH-ONLY.")
    
    svc = SandboxService()
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Create Proposal")
        with st.form("sandbox_proposal"):
            identity = st.text_input("Research Identity (e.g. Strat_MeanRev)")
            title = st.text_input("Title")
            desc = st.text_input("Description")
            
            code_template = '''def research_strategy(historical_bars, parameters):
    if not historical_bars: return None
    import pandas as pd
    df = pd.DataFrame([{"close": b.close} for b in historical_bars])
    if df.empty: return None
    
    # Custom AI Logic
    from datetime import datetime, timezone
    return TradingSignal(symbol=historical_bars[-1].symbol, direction="LONG", confidence=0.5, timestamp=datetime.now(timezone.utc), strategy="AI_Research", reason="Signal Logic")
'''
            code = st.text_area("Generated Research Code", value=code_template, height=300)
            
            if st.form_submit_button("Submit & Validate"):
                prop = svc.propose_code(identity, title, desc, code)
                
                # Mock bars for test
                from app.core.models import MarketBar
                from datetime import datetime
                bars = [MarketBar(symbol="BTC", timestamp=datetime.utcnow(), open=1, high=1, low=1, close=1, volume=1)]
                
                valid = svc.validate_proposal(prop, bars)
                if valid:
                    st.success(f"Validation Passed! Status: {prop.status.value}")
                else:
                    st.error(f"Validation Failed! Errors: {prop.assumptions}")
                    
    with col2:
        st.markdown("### Proposals & Experiments")
        proposals = svc.repo.get_proposals()
        
        for p in proposals:
            with st.expander(f"[{p.status.value}] {p.title}"):
                st.code(p.code, language="python")
                
                if p.status == ProposalStatus.SANDBOX_READY:
                    if st.button("Run Research Backtest", key=f"run_{p.proposal_id}"):
                        from app.core.models import MarketBar
                        from datetime import datetime, timedelta
                        
                        # Generate some dummy bars
                        bars = []
                        now = datetime.utcnow()
                        for i in range(10):
                            bars.append(MarketBar(symbol="BTC", timestamp=now - timedelta(days=10-i), open=100+i, high=105+i, low=95+i, close=102+i, volume=1000))
                            
                        exp = svc.run_backtest(p, "dummy_dataset", bars, {"threshold": 1.0})
                        st.write(f"Experiment {exp.status.value}. Evidence: {exp.evidence}")
                        st.rerun()
                
                if p.status == ProposalStatus.BACKTESTED:
                    if st.button("APPROVE FOR RESEARCH", key=f"approve_{p.proposal_id}"):
                        svc.approve_for_research(p.proposal_id)
                        st.rerun()
                        
                if p.status == ProposalStatus.APPROVED_FOR_RESEARCH:
                    st.success("Approved for further Research/Lessons usage.")
