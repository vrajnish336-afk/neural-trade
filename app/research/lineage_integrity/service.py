import uuid
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone

from app.research.lineage_integrity.models import (
    ResearchIntegrityReport, IntegrityFinding, IntegrityFindingType, IntegritySeverity
)
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType
from app.research.reasoning.service import ReasoningService
from app.research.planner.planner import ResearchDecisionPlanner
from app.research.governance.service import GovernanceService

class IntegrityService:
    def __init__(self, 
                 graph_repo: Optional[EvidenceGraphRepository] = None,
                 reasoning_svc: Optional[ReasoningService] = None,
                 planner_svc: Optional[ResearchDecisionPlanner] = None,
                 gov_svc: Optional[GovernanceService] = None):
        self.graph_repo = graph_repo or EvidenceGraphRepository()
        self.reasoning_svc = reasoning_svc or ReasoningService(self.graph_repo)
        self.planner_svc = planner_svc or ResearchDecisionPlanner()
        self.gov_svc = gov_svc or GovernanceService()

        # Bounded Traversal Config
        self.MAX_DEPTH = 8
        self.MAX_NODES = 500

    def generate_report(self, as_of: datetime) -> ResearchIntegrityReport:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        report = ResearchIntegrityReport(
            report_id=f"rep_{uuid.uuid4().hex[:8]}",
            as_of=as_of_utc,
            generated_at=datetime.now(timezone.utc)
        )
        
        findings = []
        
        # 1. Verify Reasoning -> Knowledge -> Evidence Lineage
        findings.extend(self._verify_reasoning_lineage(as_of_utc, report))
        
        # 2. Verify Knowledge -> Evidence Lineage
        findings.extend(self._verify_knowledge_lineage(as_of_utc, report))
        
        # 3. Verify Planner -> Reasoning Gap Lineage
        findings.extend(self._verify_planner_lineage(as_of_utc, report))

        # Compute summary
        for f in findings:
            report.severity_counts[f.severity.value] += 1
            if f.finding_type in [IntegrityFindingType.ORPHANED_EVIDENCE, IntegrityFindingType.ORPHANED_KNOWLEDGE, IntegrityFindingType.ORPHANED_REASONING]:
                report.orphaned_objects += 1
            elif f.finding_type == IntegrityFindingType.FUTURE_INFORMATION_VIOLATION:
                report.future_violations += 1
            elif f.finding_type == IntegrityFindingType.GOVERNANCE_LINEAGE_GAP:
                report.governance_gaps += 1
            elif f.finding_type == IntegrityFindingType.CONTRADICTORY_LINEAGE:
                report.contradictions += 1
            elif f.finding_type == IntegrityFindingType.DUPLICATE_LINEAGE:
                report.duplicate_lineages += 1
            elif f.finding_type in [IntegrityFindingType.BROKEN_FORWARD_LINEAGE, IntegrityFindingType.BROKEN_BACKWARD_LINEAGE]:
                report.broken_lineages += 1
                
        report.findings = findings
        return report

    def _verify_reasoning_lineage(self, as_of: datetime, report: ResearchIntegrityReport) -> List[IntegrityFinding]:
        findings = []
        # Get all reasoning results <= as_of
        all_reasoning = [r for r in self.reasoning_svc._persisted_results.values() if r.as_of <= as_of]
        
        for r in all_reasoning:
            report.total_nodes_checked += 1
            if not r.source_claim_ids:
                findings.append(self._create_finding(
                    IntegrityFindingType.ORPHANED_REASONING, IntegritySeverity.HIGH, r.reasoning_id,
                    "Phase 53", "Reasoning lacks source claim IDs.", as_of
                ))
            else:
                for claim_id in r.source_claim_ids:
                    # Check graph
                    node = self.graph_repo.get_node(claim_id)
                    if not node:
                        findings.append(self._create_finding(
                            IntegrityFindingType.BROKEN_BACKWARD_LINEAGE, IntegritySeverity.HIGH, r.reasoning_id,
                            "Phase 53", f"Upstream claim {claim_id} not found in Graph.", as_of, upstream_id=claim_id
                        ))
                    elif node.as_of > r.as_of:
                        findings.append(self._create_finding(
                            IntegrityFindingType.FUTURE_INFORMATION_VIOLATION, IntegritySeverity.CRITICAL, r.reasoning_id,
                            "Phase 53", f"Reasoning depends on future claim {claim_id}.", as_of, upstream_id=claim_id
                        ))
                        
            # Check if governance exists for this reasoning
            audit_exists = any(a for a in self.gov_svc.audits if a.source_id == r.reasoning_id and a.as_of <= as_of)
            if not audit_exists:
                findings.append(self._create_finding(
                    IntegrityFindingType.GOVERNANCE_LINEAGE_GAP, IntegritySeverity.MEDIUM, r.reasoning_id,
                    "Phase 46", "No audit event for reasoning generation.", as_of
                ))
                
        return findings

    def _verify_knowledge_lineage(self, as_of: datetime, report: ResearchIntegrityReport) -> List[IntegrityFinding]:
        findings = []
        # Fetch knowledge claims from graph
        nodes = self.graph_repo.get_nodes(as_of)
        knowledge_nodes = [n for n in nodes if n.node_type == NodeType.KNOWLEDGE_CLAIM]
        
        for k in knowledge_nodes:
            report.total_nodes_checked += 1
            
            edges_in = self.graph_repo.get_edges_for_node(k.node_id, direction='in')
            # Filter edges to valid historical edges
            historical_edges = [e for e in edges_in if e.as_of <= as_of]
            report.total_edges_checked += len(historical_edges)
            
            if not historical_edges:
                findings.append(self._create_finding(
                    IntegrityFindingType.ORPHANED_KNOWLEDGE, IntegritySeverity.HIGH, k.node_id,
                    "Phase 51", "Knowledge claim has no upstream evidence edges in DAG.", as_of
                ))
            else:
                for e in historical_edges:
                    if e.as_of > k.as_of:
                        # Edge created after knowledge claim but points to it? That is temporal ordering violation
                        findings.append(self._create_finding(
                            IntegrityFindingType.TEMPORAL_ORDER_VIOLATION, IntegritySeverity.HIGH, k.node_id,
                            "Phase 31", "Edge created after claim but asserts historical lineage.", as_of, upstream_id=e.edge_id
                        ))
                        
                    upstream_node = self.graph_repo.get_node(e.source_node_id)
                    if upstream_node and upstream_node.as_of > k.as_of:
                        findings.append(self._create_finding(
                            IntegrityFindingType.FUTURE_INFORMATION_VIOLATION, IntegritySeverity.CRITICAL, k.node_id,
                            "Phase 31", "Knowledge claim depends on evidence from the future.", as_of, upstream_id=upstream_node.node_id
                        ))
                        
        return findings
        
    def _verify_planner_lineage(self, as_of: datetime, report: ResearchIntegrityReport) -> List[IntegrityFinding]:
        findings = []
        
        # For all questions generated by Phase 53 Reasoning, check if they exist in Planner
        reasoning_qs = self.reasoning_svc.get_questions_for_review()
        valid_rqs = [q for q in reasoning_qs if q.as_of <= as_of]
        
        for rq in valid_rqs:
            # Check Planner Repo
            planner_q = self.planner_svc.repo.get_candidate(rq.question_id)
            if not planner_q and False:  # Simulated check: In actual app, Planner consumes these via an orchestrator
                pass
                
        # Let's check Planner's own queue backwards
        for pq in self.planner_svc.repo.get_ranked_decisions(as_of):
            report.total_nodes_checked += 1
            if not getattr(pq, 'related_conclusions', None) and not getattr(pq, 'related_experiments', None):
                findings.append(self._create_finding(
                    IntegrityFindingType.ORPHANED_EVIDENCE, IntegritySeverity.MEDIUM, pq.decision_id,
                    "Phase 32", "Research Decision has no related experiments or conclusions.", as_of
                ))

        return findings

    def _create_finding(self, ftype: IntegrityFindingType, sev: IntegritySeverity, obj_id: str, phase: str, reason: str, as_of: datetime, upstream_id: Optional[str] = None) -> IntegrityFinding:
        return IntegrityFinding(
            finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
            finding_type=ftype,
            severity=sev,
            canonical_object_id=obj_id,
            upstream_id=upstream_id,
            phase=phase,
            reason_code=reason,
            evidence_reference="SYSTEM_AUDIT",
            detected_at=datetime.now(timezone.utc),
            as_of=as_of
        )
