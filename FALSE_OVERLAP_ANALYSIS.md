# FALSE OVERLAP ANALYSIS

A superficial review suggested high redundancy across the 53 phases. However, repository analysis reveals that most of these are "False Overlaps"—systems that share similar terminology but execute fundamentally distinct logic or serve as critical persistence layers for downstream aggregators.

## 1. Phase 17 vs Phase 51 (Knowledge)
*   **Perceived Overlap**: Both manage "Knowledge".
*   **Reality**: Phase 17 (`app.research.knowledge_models.ResearchKnowledgeChange`) is explicitly wired into `app.research.monitoring_service.py` (Phase 20) to handle live Paper Trading degradation events. Phase 51 (`ResearchKnowledgeClaim`) is an offline canonical synthesis tool. Deleting Phase 17 breaks the Paper Monitor entirely.

## 2. Phase 23 vs Phase 51 (Lessons vs Knowledge)
*   **Perceived Overlap**: Both store research takeaways.
*   **Reality**: `app.learning` (Phase 23) is a specialized engine wired directly into `app.copilot.context` (AI retrieval), dashboard UI, and `evolution_engine` (Phase 29). `ResearchKnowledgeClaim` (Phase 51) is a strict, programmatic Graph node.

## 3. Phase 28 vs Phase 31 (Experiment Intelligence vs Evidence Graph)
*   **Perceived Overlap**: Both track experiment evidence.
*   **Reality**: Phase 28 (`ExperimentEvidenceProfile`) parses granular backtest metrics for the `evolution_engine` (Phase 29). Phase 31 (`EvidenceNode`) is a generic DAG storage layer. Merging them would pollute the generic graph with hardcoded backtest metrics.

## 4. Phase 33 vs Phase 51 (Synthesis vs Canonical Knowledge)
*   **Perceived Overlap**: Phase 51 canonical knowledge was thought to replace Phase 33 Synthesis.
*   **Reality**: Phase 51's `KnowledgeSynthesizer` physically imports `app.research.synthesis.repository` and reads `KnowledgeSynthesis` objects to build its claims. Phase 33 is the **input data source** for Phase 51. Deleting Phase 33 deletes the database records Phase 51 depends on.

## 5. Phase 37 vs Phase 45 (Consensus vs Meta-Analysis)
*   **Perceived Overlap**: Both normalize evidence and check for conflicts.
*   **Reality**: Phase 37's `EvidenceNormalizer` is imported by Phase 38 (Causality) and Phase 51 (Knowledge Intelligence) to align variables. Phase 45 uses a completely separate `MetaNormalizer` designed explicitly for calculating P-hacking and Selection Bias, not generic variable alignment.

## 6. Phase 36 vs Phase 50 (Decay/Drift vs Revalidation)
*   **Perceived Overlap**: Both govern aging research.
*   **Reality**: They are already merged physically. Both live inside `app/research/revalidation/`. There is no refactor needed; they are the same module.

## 7. Phase 32 vs Phase 53 (Planner vs Reasoning)
*   **Perceived Overlap**: Both generate research questions.
*   **Reality**: Phase 53 is a pure logic engine that generates `ResearchQuestionCandidate` objects and deposits them into Phase 32's `planner.py`. Phase 32 is the queue manager. Phase 53 is the producer.
