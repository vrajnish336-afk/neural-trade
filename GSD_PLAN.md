# GSD PLAN: PHASE 50 (Research Revalidation & Evidence Consolidation Engine)

## 1. Domain Models (`app/research/revalidation/models.py`)
- Extend `RevalidationAssessment` with `RevalidationAssessmentState` (e.g. `REVALIDATION_CONFIRMS_ORIGINAL`, `REVALIDATION_WEAKENS_ORIGINAL`).
- Add `ConsolidatedResearchEvidence` model referencing Phase 47/48/49 findings.

## 2. Evidence Consolidation (`app/research/revalidation/consolidation.py`)
- Gather evidence from Isolation, Discrepancy, and Reproduction.
- Deduplicate overlapping tests to evaluate true independent evidence strength.

## 3. Assessment & Revision Logic (`app/research/revalidation/assessment.py`)
- Deterministic logic translating consolidated evidence states into the final `RevalidationAssessmentState`.
- Trigger Phase 46 `ResearchConclusionRevision` safely (append-only).
- Trigger Phase 32 `ResearchGap` generation if `REVALIDATION_INCONCLUSIVE`.

## 4. Integration & CLI (`app/research/revalidation/service.py`, CLI, UI)
- Tie the orchestrator together.
- Add `ntrade revalidate <conclusion_id>`.
- Expand Tab 22 in `synthesis.py` to show final Revalidation status.
