from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class LineageStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BROKEN = "BROKEN"
    ORPHANED = "ORPHANED"
    CONTRADICTED = "CONTRADICTED"
    FUTURE_VIOLATION = "FUTURE_VIOLATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class IntegrityFindingType(str, Enum):
    ORPHANED_EVIDENCE = "ORPHANED_EVIDENCE"
    ORPHANED_KNOWLEDGE = "ORPHANED_KNOWLEDGE"
    ORPHANED_REASONING = "ORPHANED_REASONING"
    BROKEN_FORWARD_LINEAGE = "BROKEN_FORWARD_LINEAGE"
    BROKEN_BACKWARD_LINEAGE = "BROKEN_BACKWARD_LINEAGE"
    FUTURE_INFORMATION_VIOLATION = "FUTURE_INFORMATION_VIOLATION"
    TEMPORAL_ORDER_VIOLATION = "TEMPORAL_ORDER_VIOLATION"
    GOVERNANCE_LINEAGE_GAP = "GOVERNANCE_LINEAGE_GAP"
    GRAPH_LINEAGE_GAP = "GRAPH_LINEAGE_GAP"
    DUPLICATE_LINEAGE = "DUPLICATE_LINEAGE"
    CONTRADICTORY_LINEAGE = "CONTRADICTORY_LINEAGE"

class IntegritySeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IntegrityFinding(BaseModel):
    finding_id: str
    finding_type: IntegrityFindingType
    severity: IntegritySeverity
    canonical_object_id: str
    upstream_id: Optional[str] = None
    downstream_id: Optional[str] = None
    phase: str
    reason_code: str
    evidence_reference: str
    detected_at: datetime
    as_of: datetime
    remediation_status: str = "OPEN"
    
class ResearchIntegrityReport(BaseModel):
    report_id: str
    as_of: datetime
    generated_at: datetime
    total_nodes_checked: int = 0
    total_edges_checked: int = 0
    complete_lineages: int = 0
    partial_lineages: int = 0
    broken_lineages: int = 0
    orphaned_objects: int = 0
    future_violations: int = 0
    governance_gaps: int = 0
    contradictions: int = 0
    duplicate_lineages: int = 0
    severity_counts: Dict[str, int] = Field(default_factory=lambda: {
        "INFO": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0
    })
    findings: List[IntegrityFinding] = Field(default_factory=list)
    methodology_version: str = "lineage_integrity_v1"
