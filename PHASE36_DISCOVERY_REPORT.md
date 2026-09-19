# PHASE 36 DISCOVERY REPORT: RESEARCH EVIDENCE DECAY, DRIFT & REVALIDATION INTELLIGENCE

## 1. Discovered Architecture & Existing Staleness Logic
- The core project architecture uses a persistent Evidence Graph (Phase 31).
- **Staleness Policy**: Discovered across `app/research/planner/scoring.py` and `app/research/synthesis/synthesizer.py`. The explicit standard for staleness is `> 90 days` between the most recent supporting experiment (`created_at` / `as_of`) and the assessment evaluation time (`as_of`). We will strictly reuse the 90-day boundary for `EVIDENCE_TOO_OLD`.
- **Performance Drift**: Phase 19/20 established `app/research/drift_analyzer.py` and `PerformanceDriftAnalyzer`, which categorizes forward results vs historical results into `STABLE`, `DEGRADED`, and `SIGNIFICANTLY_DEGRADED`.
- **Phase 35 Integration**: Phase 35 determines baseline `EvidenceStrengthLevel` (STRONG, MODERATE, FRAGILE, WEAK, INSUFFICIENT) and marks risks like `MULTIPLE_TESTING_RISK`. Phase 36 will take the Phase 35 baseline and decide if it needs to be downgraded due to age or drift.

## 2. Reusable Components Identified
- `EvidenceGraph` & `EvidenceNode`: Will be used to scan for newer evidence (experiments added after the original validation).
- `HypothesisValidationResult`: The baseline state of the hypothesis.
- `ResearchReplicationResult`: Provides independent unit counts and testing risk flags.
- `PerformanceDriftAnalyzer`: For assessing quantitative decay.
- `Phase 32 Research Planner`: Will consume generated `ResearchEvidenceGap` items if revalidation is flagged.

## 3. Planned Phase 36 Architecture
- `app/research/revalidation/` containing `decay.py`, `drift.py`, `revalidation.py`, `models.py`, `repository.py`, and `service.py`.
- **Decay Engine**: Deterministically calculates evidence age (days since last supporting experiment).
- **Drift Engine**: Compares baseline evidence metadata (regimes, methodology version) against any newer evidence. If an experiment uses a new regime, flags `NEW_REGIME`. If the methodology version strings differ, flags `METHODOLOGY_CHANGED`.
- **Revalidation Engine**: Synthesizes the decay and drift flags. Emits specific Revalidation Reasons (e.g., `EVIDENCE_TOO_OLD`, `METHODOLOGY_CHANGED`, `NEW_CONTRADICTION`).
- **Safety Boundary**: This engine ONLY suggests revalidation; it does NOT automatically run backtests. It creates an explicit gap to be picked up by the Planner, demanding human review.

## 4. Risks & Duplication Avoidance
- Do NOT rewrite `PerformanceDriftAnalyzer`.
- Do NOT rewrite `EvidenceStrengthLevel` calculation; rather, apply a modifier that degrades it (e.g., `STRONG` -> `STALE` or `REQUIRES_REVALIDATION`).
- Ensure `as_of` correctly scopes the newer evidence traversal so historical reproduction remains perfectly intact.
