import streamlit as st
import pandas as pd
from app.research.evidence_graph.builder import GraphBuilder
from app.research.evidence_graph.queries import GraphQueries

def render_evidence_graph_tab(conn):
    st.markdown("## PHASE 31: EVIDENCE GRAPH & KNOWLEDGE LINEAGE")
    st.warning("PAPER / RESEARCH ONLY. KNOWLEDGE LINEAGE ONLY. NO CAUSAL CLAIMS UNLESS DETERMINISTICALLY SUPPORTED.")
    
    if st.button("Rebuild Graph from Source Data"):
        with st.spinner("Building deterministic graph..."):
            builder = GraphBuilder()
            builder.build_graph()
            st.success("Graph built successfully.")
            
    st.markdown("---")
    
    queries = GraphQueries()
    res = queries.validate_graph()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Nodes", res["total_nodes"])
    c2.metric("Total Edges", res["total_edges"])
    c3.metric("Status", res["status"])
    
    st.markdown("---")
    st.markdown("### Search Node Lineage")
    
    node_id = st.text_input("Enter Node ID (e.g. comp_XYZ, exp_XYZ, prop_XYZ)")
    
    if node_id:
        chain = queries.get_evidence_chain(node_id)
        if chain:
            st.markdown("#### Evidence Chain (Upstream)")
            df = pd.DataFrame([{
                "Step": i,
                "Node ID": n.node_id,
                "Type": n.node_type.value,
                "Source ID": n.source_id,
                "As Of": n.as_of.isoformat()
            } for i, n in enumerate(chain)])
            st.dataframe(df, use_container_width=True)
            
            st.markdown("#### Supporting Evidence")
            supporting = queries.get_supporting_evidence(node_id)
            if supporting:
                st.dataframe(pd.DataFrame([{"Node": s.node_id, "Type": s.node_type.value} for s in supporting]))
            else:
                st.info("No supporting evidence found.")
                
            st.markdown("#### Contradicting Evidence")
            contradicting = queries.get_contradicting_evidence(node_id)
            if contradicting:
                st.dataframe(pd.DataFrame([{"Node": c.node_id, "Type": c.node_type.value} for c in contradicting]))
            else:
                st.info("No contradicting evidence found.")
        else:
            st.warning("Node not found or has no upstream lineage.")
