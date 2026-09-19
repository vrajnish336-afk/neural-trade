import argparse
from datetime import datetime
import json
from app.research.evidence_graph.builder import GraphBuilder
from app.research.evidence_graph.queries import GraphQueries

def setup_evidence_graph_parser(subparsers):
    p = subparsers.add_parser("evidence-graph-build", help="Idempotently build the evidence graph")
    p.set_defaults(func=run_build)
    
    p2 = subparsers.add_parser("evidence-graph-validate", help="Validate graph integrity")
    p2.set_defaults(func=run_validate)
    
    p3 = subparsers.add_parser("evidence-chain", help="Get evidence chain for a node")
    p3.add_argument("node_id", help="Node ID")
    p3.set_defaults(func=run_chain)

def run_build(args) -> int:
    print("Building evidence graph deterministically from existing sources...")
    builder = GraphBuilder()
    builder.build_graph()
    
    queries = GraphQueries()
    res = queries.validate_graph()
    print(f"Graph built successfully. Nodes: {res['total_nodes']}, Edges: {res['total_edges']}")
    return 0

def run_validate(args) -> int:
    queries = GraphQueries()
    res = queries.validate_graph()
    print(json.dumps(res, indent=2))
    return 0 if res["status"] == "VALID" else 1

def run_chain(args) -> int:
    queries = GraphQueries()
    chain = queries.get_evidence_chain(args.node_id)
    if not chain:
        print("No chain found.")
        return 0
        
    for i, node in enumerate(chain):
        print(f"[{i}] {node.node_type.value}: {node.source_id}")
    return 0
