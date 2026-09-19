import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship
from app.research.knowledge_intelligence.models import ResearchKnowledgeClaim, KnowledgeGap, KnowledgePattern, KnowledgeState
from app.research.governance.service import GovernanceService
from app.research.governance.models import ResearchAuditEvent

class KnowledgeGraphBuilder:
    def __init__(self, graph_repo: EvidenceGraphRepository, governance_service: GovernanceService):
        self.graph_repo = graph_repo
        self.gov_service = governance_service

    def _deterministic_hash(self, *args) -> str:
        s = "_".join(str(a) for a in args)
        return hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]

    def _save_node_idempotent(self, node: EvidenceNode):
        existing = self.graph_repo.get_node(node.node_id)
        if not existing:
            self.graph_repo.save_node(node)
            return True
        return False

    def _save_edge_idempotent(self, edge: EvidenceEdge):
        existing = [e for e in self.graph_repo.get_edges_for_node(edge.source_node_id, direction='out') if e.edge_id == edge.edge_id]
        if not existing:
            self.graph_repo.save_edge(edge)
            return True
        return False

    def build_from_claims(self, claims: List[ResearchKnowledgeClaim], as_of: datetime) -> int:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        edges_created = 0
        
        for claim in claims:
            if claim.as_of > as_of_utc:
                continue
                
            claim_node = EvidenceNode(
                node_id=claim.claim_id,
                node_type=NodeType.KNOWLEDGE_CLAIM,
                source_id=claim.claim_id,
                source_type="ResearchKnowledgeClaim",
                identity_hash=self._deterministic_hash("KNOWLEDGE_CLAIM", claim.claim_id),
                created_at=claim.created_at,
                as_of=claim.as_of,
                metadata={"state": claim.knowledge_state.value, "statement": claim.canonical_statement}
            )
            self._save_node_idempotent(claim_node)
            
            # Scopes -> CONDITIONED_ON
            for reg in claim.scope.regime_scope:
                reg_id = self._deterministic_hash("REGIME", reg)
                reg_node = EvidenceNode(
                    node_id=reg_id, node_type=NodeType.REGIME, source_id=reg, source_type="Scope",
                    identity_hash=reg_id, created_at=claim.created_at, as_of=claim.as_of, metadata={"name": reg}
                )
                self._save_node_idempotent(reg_node)
                
                edge_id = self._deterministic_hash(claim_node.node_id, EdgeRelationship.CONDITIONED_ON.value, reg_id)
                edge = EvidenceEdge(
                    edge_id=edge_id, source_node_id=claim_node.node_id, target_node_id=reg_id,
                    relationship_type=EdgeRelationship.CONDITIONED_ON, evidence_basis=claim.claim_id,
                    created_at=claim.created_at, as_of=claim.as_of, deterministic_key=edge_id
                )
                if self._save_edge_idempotent(edge):
                    edges_created += 1

            for ds in claim.scope.dataset_scope:
                ds_id = self._deterministic_hash("DATASET", ds)
                ds_node = EvidenceNode(
                    node_id=ds_id, node_type=NodeType.DATASET, source_id=ds, source_type="Scope",
                    identity_hash=ds_id, created_at=claim.created_at, as_of=claim.as_of, metadata={"name": ds}
                )
                self._save_node_idempotent(ds_node)
                
                edge_id = self._deterministic_hash(claim_node.node_id, EdgeRelationship.CONDITIONED_ON.value, ds_id)
                edge = EvidenceEdge(
                    edge_id=edge_id, source_node_id=claim_node.node_id, target_node_id=ds_id,
                    relationship_type=EdgeRelationship.CONDITIONED_ON, evidence_basis=claim.claim_id,
                    created_at=claim.created_at, as_of=claim.as_of, deterministic_key=edge_id
                )
                if self._save_edge_idempotent(edge):
                    edges_created += 1

            # CONFLICTS handling
            if claim.knowledge_state == KnowledgeState.CONFLICTED:
                # E.g., if there's contradicting evidence, link to it
                for c_ev_id in claim.contradicting_evidence_ids:
                    edge_id = self._deterministic_hash(claim_node.node_id, EdgeRelationship.CONTRADICTS.value, c_ev_id)
                    edge = EvidenceEdge(
                        edge_id=edge_id, source_node_id=claim_node.node_id, target_node_id=c_ev_id,
                        relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis=claim.claim_id,
                        created_at=claim.created_at, as_of=claim.as_of, deterministic_key=edge_id
                    )
                    if self._save_edge_idempotent(edge):
                        edges_created += 1
                        
        if edges_created > 0:
            self.gov_service.audits.append(ResearchAuditEvent(
                event_type="KNOWLEDGE_GRAPH_EDGES_CREATED",
                research_identity_hash="graph_builder",
                source_id="builder",
                reason=f"Added {edges_created} edges from claims",
                as_of=as_of_utc
            ))
        return edges_created

    def build_from_patterns(self, patterns: List[KnowledgePattern], claims: List[ResearchKnowledgeClaim], as_of: datetime) -> int:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        edges_created = 0
        
        for p in patterns:
            if p.as_of > as_of_utc:
                continue
                
            pat_node = EvidenceNode(
                node_id=p.pattern_id,
                node_type=NodeType.KNOWLEDGE_PATTERN,
                source_id=p.pattern_id,
                source_type="KnowledgePattern",
                identity_hash=self._deterministic_hash("KNOWLEDGE_PATTERN", p.pattern_id),
                created_at=p.created_at,
                as_of=p.as_of,
                metadata={"family": p.pattern_family.value, "description": p.description}
            )
            self._save_node_idempotent(pat_node)
            
            # Map pattern to relevant datasets/claims
            for ds in p.datasets_involved:
                ds_id = self._deterministic_hash("DATASET", ds)
                edge_id = self._deterministic_hash(pat_node.node_id, EdgeRelationship.SHARES_FAILURE_MODE.value, ds_id)
                edge = EvidenceEdge(
                    edge_id=edge_id, source_node_id=pat_node.node_id, target_node_id=ds_id,
                    relationship_type=EdgeRelationship.SHARES_FAILURE_MODE, evidence_basis=p.pattern_id,
                    created_at=p.created_at, as_of=p.as_of, deterministic_key=edge_id
                )
                if self._save_edge_idempotent(edge):
                    edges_created += 1
                    
        return edges_created

    def build_from_gaps(self, gaps: List[KnowledgeGap], as_of: datetime) -> int:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        edges_created = 0
        
        for g in gaps:
            if g.as_of > as_of_utc:
                continue
                
            gap_node = EvidenceNode(
                node_id=g.gap_id,
                node_type=NodeType.RESEARCH_GAP,
                source_id=g.gap_id,
                source_type="KnowledgeGap",
                identity_hash=self._deterministic_hash("RESEARCH_GAP", g.gap_id),
                created_at=g.created_at,
                as_of=g.as_of,
                metadata={"reason": g.reason, "required_evidence": g.required_evidence_type}
            )
            self._save_node_idempotent(gap_node)
            
            if g.claim_id:
                edge_id = self._deterministic_hash(g.claim_id, EdgeRelationship.EXPOSES_GAP.value, g.gap_id)
                edge = EvidenceEdge(
                    edge_id=edge_id, source_node_id=g.claim_id, target_node_id=g.gap_id,
                    relationship_type=EdgeRelationship.EXPOSES_GAP, evidence_basis=g.gap_id,
                    created_at=g.created_at, as_of=g.as_of, deterministic_key=edge_id
                )
                if self._save_edge_idempotent(edge):
                    edges_created += 1
                    
        return edges_created
