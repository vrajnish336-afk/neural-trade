import argparse
from datetime import datetime, timezone
from app.research.lineage_integrity.service import IntegrityService

def setup_lineage_parser(subparsers):
    p = subparsers.add_parser("lineage", help="Research Lineage Integrity Layer (Phase 54)")
    sub = p.add_subparsers(dest="lineage_command")
    
    verify_p = sub.add_parser("verify", help="Run full lineage verification")
    verify_p.set_defaults(func=run_lineage_verify)
    
def run_lineage_verify(args) -> int:
    print("WARNING: PAPER / RESEARCH ONLY — LIVE TRADING DISABLED")
    print("Running Research Lineage Integrity Verification...\n")
    
    svc = IntegrityService()
    as_of = datetime.now(timezone.utc)
    report = svc.generate_report(as_of)
    
    print(f"Total Nodes Checked: {report.total_nodes_checked}")
    print(f"Total Edges Checked: {report.total_edges_checked}")
    print(f"Orphaned Objects: {report.orphaned_objects}")
    print(f"Future Violations: {report.future_violations}")
    print(f"Governance Gaps: {report.governance_gaps}")
    
    print("\nSeverity Counts:")
    for sev, count in report.severity_counts.items():
        print(f"  {sev}: {count}")
        
    print("\nTop Findings:")
    for f in report.findings[:10]:
        print(f"[{f.severity.value}] {f.finding_type.value} on {f.canonical_object_id} ({f.reason_code})")
        
    return 0
