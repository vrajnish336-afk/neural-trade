import streamlit as st
from app.research.models import ResearchExperiment

def render_lineage_component(experiment: ResearchExperiment):
    """
    Renders the ResearchLineage in a clean expander to show the exact historical
    execution context of the experiment without cluttering the main UI.
    """
    if not experiment.lineage:
        st.warning("Lineage not available for this legacy experiment.")
        return
        
    lin = experiment.lineage
    
    with st.expander("🔍 RESEARCH LINEAGE (Execution Context)", expanded=False):
        st.markdown("### Execution-Time Snapshot")
        st.markdown("This data represents the exact immutable context captured when the experiment ran.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 1. Code & Environment")
            st.json({
                "python_version": lin.environment.python_version,
                "os": lin.environment.os_name,
                "commit": lin.code.commit_hash or "Unknown",
                "is_dirty": lin.code.is_dirty if lin.code.is_dirty is not None else "Unknown"
            })
            
            st.markdown("#### 2. Strategy")
            st.json({
                "name": lin.strategy.strategy_name,
                "parameters": lin.strategy.parameters
            })
            
        with col2:
            st.markdown("#### 3. Configuration & Costs")
            st.json({
                "capital": lin.configuration.capital,
                "cost_model": lin.configuration.cost_model,
                "risk_model": lin.configuration.risk_model
            })
            
            st.markdown("#### 4. Data & Randomness")
            st.json({
                "dataset_hash": experiment.dataset_identity.get("hash"),
                "symbol": experiment.dataset_identity.get("symbol"),
                "seed": experiment.random_seed
            })
