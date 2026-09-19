from typing import List, Optional
from datetime import datetime
from app.research.governance.models import (
    ResearchReproducibilityManifest, ResearchConclusionRevision, 
    ResearchAuditEvent, ResearchGovernanceStatus, GovernanceState
)
from app.research.governance.reproducibility import ReproducibilityVerifier
from app.research.governance.regression import ResearchRegressionDetector
from app.research.governance.change_detection import ResearchChangeDetector

class GovernanceService:
    def __init__(self):
        self.manifests = []
        self.revisions = []
        self.audits = []
        
    def log_manifest(self, manifest: ResearchReproducibilityManifest):
        self.manifests.append(manifest)
        self.audits.append(ResearchAuditEvent(
            event_type="MANIFEST_CREATED",
            research_identity_hash=manifest.research_identity_hash,
            source_id=manifest.manifest_id,
            reason="Manifest recorded",
            as_of=manifest.as_of
        ))
        
    def revise_conclusion(self, new_rev: ResearchConclusionRevision, old_rev: Optional[ResearchConclusionRevision] = None, change_cat = None):
        self.revisions.append(new_rev)
        
        event_type = "CONCLUSION_CREATED"
        reason = "Initial conclusion"
        if old_rev:
            event_type = "CONCLUSION_REVISED"
            reason = f"Conclusion changed. Context: {change_cat.value if change_cat else 'UNKNOWN'}"
            if change_cat and ResearchRegressionDetector.detect_regression(old_rev.conclusion_state, new_rev.conclusion_state, change_cat):
                self.audits.append(ResearchAuditEvent(
                    event_type="REGRESSION_DETECTED",
                    research_identity_hash=new_rev.research_identity_hash,
                    source_id=new_rev.revision_id,
                    reason="Unexplained degradation of conclusion without input change",
                    as_of=new_rev.as_of
                ))
                
        self.audits.append(ResearchAuditEvent(
            event_type=event_type,
            research_identity_hash=new_rev.research_identity_hash,
            source_id=new_rev.revision_id,
            reason=reason,
            as_of=new_rev.as_of
        ))
