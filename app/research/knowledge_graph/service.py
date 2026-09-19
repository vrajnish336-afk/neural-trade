from datetime import datetime, timezone
from typing import List
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.governance.service import GovernanceService
from app.research.knowledge_intelligence.models import ResearchKnowledgeClaim, KnowledgeGap, KnowledgePattern
from app.research.knowledge_graph.builder import KnowledgeGraphBuilder
from app.research.knowledge_graph.queries import KnowledgeGraphQueries
from app.research.knowledge_graph.models import KnowledgePath, KnowledgeCluster, GraphSummary

class KnowledgeGraphService:
    def __init__(self, graph_repo: EvidenceGraphRepository = None, gov_service: GovernanceService = None):
        self.graph_repo = graph_repo or EvidenceGraphRepository()
        self.gov_service = gov_service or GovernanceService()
        self.builder = KnowledgeGraphBuilder(self.graph_repo, self.gov_service)
        self.queries = KnowledgeGraphQueries(self.graph_repo)

    def ingest_knowledge(self, claims: List[ResearchKnowledgeClaim], patterns: List[KnowledgePattern], gaps: List[KnowledgeGap], as_of: datetime) -> int:
        """Deterministically insert Phase 51 knowledge into Phase 31 infrastructure."""
        count = 0
        count += self.builder.build_from_claims(claims, as_of)
        count += self.builder.build_from_patterns(patterns, claims, as_of)
        count += self.builder.build_from_gaps(gaps, as_of)
        return count

    def get_summary(self, as_of: datetime) -> GraphSummary:
        return self.queries.get_historical_graph_summary(as_of)

    def trace_claim_relationships(self, claim_id: str, as_of: datetime) -> List[KnowledgePath]:
        return self.queries.get_related_claims(claim_id, as_of)

    def identify_structural_failures(self, as_of: datetime) -> List[KnowledgeCluster]:
        return self.queries.get_failure_clusters(as_of)
