# PHASE 46 DISCOVERY REPORT: RESEARCH EVIDENCE GOVERNANCE & REPRODUCIBILITY CONTROL PLANE

## 1. Existing Infrastructure Analysis
- **Phase 1-16 (Core Persistence/Config)**: Exists for parameters and configuration logic.
- **Phase 31 (Evidence Graph)**: Lineage tracking exists from `EvidenceNode` -> `EvidenceEdge`.
- **Phase 32 (Planner)**: Generates explicit `ResearchPriorityBreakdown` to route new gaps.
- **Phase 35, 36, 38 (Replication, Decay, Causality)**: Bounded assessments that feed into Phase 45.
- **Phase 45 (Meta-Analysis)**: Generates the overarching `MetaResearchConclusion` containing states like `ESTABLISHED_WITHIN_TESTED_SCOPE`, strictly filtered by `as_of`.

## 2. Identified Governance Gaps (What Phase 46 Adds)
Currently, a `MetaResearchConclusion` is a snapshot of truth at `as_of`. If a developer tweaks a strategy parameter, updates a risk methodology, or shifts the raw source datasets, the overarching system has no deterministic concept of "Research Regression" or "Methodology Drift." It lacks:
1. **ResearchReproducibilityManifest**: A hard deterministic fingerprint mapping the exact code, parameters, dataset, and methodology version used.
2. **ResearchConclusionRevision**: An append-only historical tracker explicitly tracking *why* a conclusion changed between `as_of` boundaries.
3. **Reproducibility Verifier & Regression Detector**: Algorithms determining if a previously accepted truth is broken because of a code change, and throwing a `GOVERNANCE_WARNING` when inputs are unchanged but the output degrades.

## 3. Integration Strategy
- **Package Creation**: We will create `app/research/governance/`.
- **Dataset & Config Fingerprinting**: Hash structures explicitly excluding volatile runtime or sensitive values (API keys/secrets).
- **Change Detection**: Strict deterministic `ResearchChangeDetector` identifying `PARAMETERS_CHANGED`, `METHODOLOGY_CHANGED`, etc.
- **Append-Only Tracking**: Instead of overwriting Phase 45 conclusions, Phase 46 versions them with full changelogs tracking why consensus shifted.

## 4. Mandatory Constraints
- NO AUTOMATIC STRATEGY DEPLOYMENT.
- MUST NOT rerun dangerous/expensive jobs automatically; merely flags them for the Phase 32 planner queue.
- Must remain strictly paper/research isolated. No live execution loops.
