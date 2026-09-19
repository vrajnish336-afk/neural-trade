# PHASE DEPENDENCY GRAPH

Based on raw repository inspection (imports, class usages, and module structures), the following dependency graph outlines the *actual* runtime wiring of the research architecture.

## 1. Early Research State & Paper Monitoring (Phases 17-20)
*   `app.research.knowledge_models` (Phase 17)
    *   **Direct Consumers**: `app.research.monitoring_service` (Phase 20). The paper monitor emits `ResearchKnowledgeChange` events when strategies degrade.
    *   **Tests**: `test_ai_research_knowledge.py` requires these models.

## 2. Evolution & Lessons (Phases 23, 28, 29)
*   `app.learning` (Phase 23 - Lesson Engine)
    *   **Direct Consumers**: `app.copilot.context`, `app.cli.commands.evolution`, `app.cli.commands.learning`, `app.dashboard.components.learning`, `app.research.continuous_orchestrator`.
*   `app.research.experiment_intelligence` (Phase 28)
    *   **Direct Consumers**: `app.learning.evolution_engine` (Phase 29). It depends on experiment-level intelligence to evolve parameters safely.

## 3. Core Synthesis & Knowledge (Phases 33, 37, 51)
*   `app.research.synthesis` (Phase 33)
    *   **Direct Consumers**: `app.research.hypothesis_validation.validator` (Phase 34), `app.research.knowledge_intelligence.synthesizer` (Phase 51). Phase 51 physically imports `SynthesisRepository` to pull upstream hypotheses into canonical knowledge claims.
*   `app.research.consensus` (Phase 37)
    *   **Direct Consumers**: `app.research.causality.service` (Phase 38), `app.research.knowledge_intelligence.synthesizer` (Phase 51). Phase 51 explicitly imports `EvidenceNormalizer` from Phase 37. Phase 38 relies on Consensus to isolate causal variables.

## 4. Revalidation & Discrepancy (Phases 36, 48, 49, 50)
*   `app.research.revalidation` (Phases 36 & 50)
    *   **Structure**: Phase 36 (`decay.py`, `drift.py`) and Phase 50 (`consolidation_service.py`) share the exact same Python package. They are already merged physically.
    *   **Direct Consumers**: `app.research.knowledge_intelligence.synthesizer` (Phase 51). Phase 51 queries `RevalidationRepository` to apply downgrades.

## 5. Reasoning & Planning (Phases 31, 32, 52, 53)
*   `app.research.evidence_graph` (Phase 31)
    *   **Direct Consumers**: Phase 37 (Normalizer), Phase 51 (Knowledge Claims), Phase 52 (Knowledge Graph), Phase 53 (Reasoning Engine).
*   `app.research.planner` (Phase 32)
    *   **Direct Consumers**: `continuous_orchestrator.py` (Phase 30), `reasoning.service.py` (Phase 53), `portfolio_discovery.py` (Phase 44).
*   `app.research.reasoning` (Phase 53)
    *   **Direct Inputs**: `EvidenceGraphRepository` (Phase 31), `ResearchKnowledgeClaim` (Phase 51).
    *   **Direct Outputs**: `ResearchQuestionCandidate` (Phase 32), `GovernanceService` (Phase 46).

## Summary
The graph is tightly coupled. Later intelligence phases (51, 52, 53) are **orchestration/aggregator layers**, not replacement layers. They depend strictly on the persistence models of the older phases (33, 37, 50).
