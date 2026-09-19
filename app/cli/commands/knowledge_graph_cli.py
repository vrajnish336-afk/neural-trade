import argparse
from datetime import datetime, timezone
from app.research.knowledge_graph.service import KnowledgeGraphService

def setup_knowledge_graph_parser(subparsers):
    p = subparsers.add_parser("knowledge-graph", help="Query and manage the Research Knowledge Relationship Graph")
    sub = p.add_subparsers(dest="kg_command")
    
    status_p = sub.add_parser("status", help="Get summary of the Knowledge Graph")
    status_p.set_defaults(func=run_kg_status)
    
    trace_p = sub.add_parser("trace", help="Trace relationships for a specific claim")
    trace_p.add_argument("claim_id", help="Knowledge Claim ID")
    trace_p.set_defaults(func=run_kg_trace)

def run_kg_status(args) -> int:
    print("WARNING: KNOWLEDGE GRAPH — RESEARCH INTELLIGENCE ONLY")
    print("WARNING: PAPER / RESEARCH ONLY — LIVE TRADING DISABLED")
    
    svc = KnowledgeGraphService()
    as_of = datetime.now(timezone.utc)
    summary = svc.get_summary(as_of)
    
    print("\nKnowledge Graph Summary:")
    print(f"Total Nodes (Knowledge Scope): {summary.total_nodes}")
    print(f"Total Relationships: {summary.total_edges}")
    print(f"Supported Relationships: {summary.supported_relationships}")
    print(f"Conflicted Relationships: {summary.conflicted_relationships}")
    print(f"Conditional Relationships: {summary.conditional_relationships}")
    print(f"Unresolved Gaps: {summary.unresolved_gaps}")
    print(f"Recurring Failure Clusters: {summary.recurring_failure_clusters}")
    return 0

def run_kg_trace(args) -> int:
    print(f"Tracing relationships for Claim: {args.claim_id}")
    svc = KnowledgeGraphService()
    as_of = datetime.now(timezone.utc)
    
    paths = svc.trace_claim_relationships(args.claim_id, as_of)
    if not paths:
        print("No relationships found.")
        return 0
        
    for p in paths:
        print(f"\nPath found:")
        path_str = f"[{p.source_node.node_type.value}] {p.source_node.node_id}"
        for i, e in enumerate(p.edges):
            path_str += f"\n  -> {e.relationship_type.value} -> [{p.nodes[i+1].node_type.value}] {p.nodes[i+1].node_id}"
        print(path_str)
        print(f"Explanation: {p.explanation}")
    return 0
