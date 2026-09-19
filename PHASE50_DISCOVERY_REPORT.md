# PHASE 50 DISCOVERY REPORT: RESEARCH REVALIDATION & EVIDENCE CONSOLIDATION ENGINE

## 1. Existing Revalidation Architecture (Phase 36)
The package `app/research/revalidation` exists and contains `models.py` (with `RevalidationAssessment`), `decay.py`, `drift.py`, `revalidation.py`. It focused on age (Decay) and market regime/performance changes (Drift). 

## 2. Evidence Architecture 
- **Phase 37**: Handles Conflict/Consensus (`EvidenceNormalizer`).
- **Phase 46**: Handles Conclusion revisions (`ResearchConclusionRevision` inside `GovernanceService`).
- **Phase 47**: `ComparisonState` (e.g. `STRUCTURAL_DIFFERENCE`).
- **Phase 48**: `ImpactAssessment` (e.g. `MODERATE_IMPACT`).
- **Phase 49**: `IsolationComparison` (e.g. `ISOLATION_SUPPORTED`).

## 3. What Phase 50 Adds
Phase 50 will extend `RevalidationAssessment` to include the formal state representing the consequence of reproduction failures (e.g., `REVALIDATION_WEAKENS_ORIGINAL`). It integrates Evidence Consolidation logic inside `app/research/revalidation/consolidation.py` to evaluate Phase 49 OFAT impacts against the historical conclusion, issuing Phase 46 revisions if the structural integrity was invalidated.

## 4. What Phase 50 Explicitly Does Not Add
- It does not generate new Evidence Graph nodes (it reuses Phase 31).
- It does not automatically optimize or mutate parameters based on the revalidation status.
- It does not rewrite original conclusions silently (it enforces append-only Phase 46 revisions).
