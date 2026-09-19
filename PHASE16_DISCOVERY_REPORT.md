# PHASE 16 DISCOVERY REPORT: RESEARCH INTELLIGENCE & DECISION LAYER

## 1. Baseline Test Metrics
- **BASELINE_TEST_COUNT**: 182
- **Passed**: 182
- **Failed**: 0
- **Skipped**: 0

## 2. Current Architecture & Data Flow
Currently, the pipeline flows as follows:
1. **AI Analysis** parses news into a structured hypothesis.
2. **Phase 14 Opportunity Intelligence** assigns an `identity_hash` to the hypothesis, deduplicates it, and scores its priority.
3. **Phase 15 Continuous Orchestrator** pulls from the queue and deterministically executes backtests.
4. **Phase 7 Evidence & Phase 8 Consistency** rigorously evaluate each *single experiment* to output an `EvidenceSummary` (STRONG, MODERATE, WEAK, INSUFFICIENT).

**Architectural Gaps**:
- We have evaluations for *individual experiments*, but we lack a macro-level **Research Conclusion** that aggregates all historical experiments tied to a single `identity_hash`.
- We lack explicit **Contradiction Detection** across multiple runs of the same hypothesis.
- We lack a mechanism to track explicit **Research Relationships** (e.g., Exp A contradicts Exp B).
- We lack a **Next Research Action** generator that translates the current evidence state into a concrete, allowable bounded research step.
- AI narrative interpretation is missing from the final output loop.

## 3. Proposed Phase 16 Architecture

### A. Data Models (`app/research/decision_models.py`)
- `ResearchConfidenceState`: `LOW`, `MODERATE`, `HIGH`, `UNRESOLVED`
- `ResearchDecisionState`: `INSUFFICIENT_EVIDENCE`, `RESEARCH_LIMITED`, `MIXED_EVIDENCE`, `CONTRADICTORY_EVIDENCE`, `SUPPORTED_FOR_FURTHER_RESEARCH`, `RESEARCH_RESULT_SUPPORTED`, `SOFTWARE_OR_ACCOUNTING_ISSUE`, `BLOCKED`
- `NextResearchAction`: Explicit enum-backed actions (e.g. `COLLECT_MORE_DATA`, `RUN_COST_STRESS`, `INSPECT_CONFLICT`).
- `ResearchConflict`: Tracks contradictory findings between two experiments.
- `ResearchRelationship`: Tracks logical relationships (e.g., `CONTRADICTS`, `SUPPORTS`).
- `ResearchConclusion`: The final synthesized macro-document.

### B. SQLite Schema (`app/database/schema.py`)
New tables:
- `research_conclusions`: Stores immutable, versioned conclusions for an `identity_hash`.
- `research_conflicts`: Stores explicitly identified conflicts.
- `research_relationships`: Graph-lite table (`source_id`, `target_id`, `relationship_type`).

### C. Evaluation Logic (`app/research/decision_engine.py`)
1. **Gather**: Fetch all experiments associated with the `identity_hash` via the orchestrator/memory layer.
2. **Compare**: Use the existing Phase 8 `CrossExperimentComparator` to detect `COMPARABLE` experiments.
3. **Conflict Check**: If comparable experiments yield differing conclusions (e.g. STRONG vs WEAK), generate a `ResearchConflict`.
4. **Aggregate**: Synthesize the `EvidenceSummary` objects into a single `ResearchConclusion`.
   - If conflicts exist: `CONTRADICTORY_EVIDENCE` / `UNRESOLVED`.
   - If insufficient: `INSUFFICIENT_EVIDENCE` / `LOW`.
   - If consistently strong: `RESEARCH_RESULT_SUPPORTED` / `HIGH`.
5. **Action Generation**: Recommend a deterministic `NextResearchAction` based on the weakest link (e.g. if regime coverage is bad, action = `TEST_ANOTHER_REGIME`).
6. **AI Narrative**: Safely pass the deterministic conclusion to the AI to generate a human-readable summary, storing it alongside the hard deterministic facts.

### D. Security & Safety Risks
- **Risk**: The AI narrative overwrites deterministic facts.
  - **Mitigation**: The AI output is stored as a purely supplementary `ai_explanation` field. It cannot alter the `decision_state` enum.
- **Risk**: The Next Research Action executes automatically.
  - **Mitigation**: The action is purely advisory. Phase 15 orchestrator still requires explicit queueing.
- **LIVE_TRADING**: Explicitly remains `False`.

### E. Next Steps (GSD Implementation)
1. Create `decision_models.py`.
2. Update `schema.py`.
3. Build `decision_engine.py` (Aggregation, Conflict Detection, AI Narrative).
4. Build CLI commands & Dashboard UI.
5. Write extensive tests for contradictions and confidence logic.
