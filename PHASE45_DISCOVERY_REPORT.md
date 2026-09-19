# PHASE 45 DISCOVERY REPORT: RESEARCH META-ANALYSIS & CROSS-EXPERIMENT EVIDENCE SYNTHESIS

## 1. Existing Infrastructure Analysis
- **Phase 35 (Replication / Generalization)**: Exposes `ReplicationCategory` (e.g., `SAME_DATASET_REPLAY`, `UNSEEN_DATA`) and `EvidenceStrengthLevel`.
- **Phase 36 (Decay / Drift)**: Tracks evidence decay and revalidation states.
- **Phase 37 (Consensus)**: Maps `ConsensusState` (`CONDITIONAL_CONSENSUS`, `CONFLICTED`) and conflict severity.
- **Phase 38 (Causality)**: Implements causal limitations prohibiting correlations from upgrading to proven mechanisms blindly.
- **Phase 43/44 (Portfolio Stress & Discovery)**: Provides portfolio-level `PortfolioFailureAssessment` and dynamically generated research gaps.
- **Phase 32 (Planner)**: Manages `ResearchDecision` and prioritizations based on information gain heuristics.

## 2. Identified Research Gaps (What Phase 45 Adds)
Currently, there are many distinct specialized validation modules (consensus, replication, portfolio intelligence, causal limits) outputting isolated states. The system lacks a definitive overarching deterministic *meta-analysis* engine that:
1. Translates disparate underlying modules into a single normalized `MetaEvidenceUnit`.
2. Strictly calculates cross-system Evidence Independence (preventing multiple identical overlapping tests from faking strong statistical support).
3. Produces a single verifiable `MetaResearchConclusion` summarizing the definitive highest-level scientific state (`ESTABLISHED_WITHIN_TESTED_SCOPE`, `SUPPORTED_BUT_CONDITIONAL`, etc.).

## 3. Integration Strategy
- **Package Creation**: We will create `app/research/meta_analysis/`.
- **Evidence Normalization**: `MetaEvidenceUnit` unifies properties like dataset identities, `as_of`, seeds, and regimes across the differing specialized modules.
- **Independence & Synthesis Engines**: Deterministic logic rejecting simple duplicate runs while propagating `MULTIPLE_TESTING_RISK` and `SELECTION_BIAS_RISK`.
- **Causality Firewall**: Meta-analysis is hard-coded to respect Phase 38 causal constraints.

## 4. Mandatory Constraints
- NO AUTOMATIC OPTIMIZER.
- NO LIVE TRADING boundaries enforced.
- Negative, null, and conflicting results MUST be preserved unconditionally (no silent pruning for "better" overall stats).
- `as_of` boundaries must explicitly block future-data leakage.
