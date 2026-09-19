# PHASE 33 DISCOVERY REPORT: RESEARCH KNOWLEDGE SYNTHESIS & CONTROLLED HYPOTHESIS GENERATION

## 1. Existing Architecture & Evidence Sources
Based on an inspection of the codebase:
- **Phase 31 (Evidence Graph)**: Contains `EvidenceNode` and `EvidenceEdge`. Edge relationships like `SUPPORTS`, `CONTRADICTS`, `VALIDATES` exist. Nodes track `EXPERIMENT`, `EVIDENCE_GAP`, `LESSON`, `OBSERVATION`.
- **Phase 32 (Research Planner)**: Generates `ResearchQuestionCandidate` from evidence gaps and assigns priority via `ResearchDecision`.
- **Phase 30 (Continuous Orchestrator)**: Pulls `APPROVED_FOR_RESEARCH` decisions to generate sandbox proposals.
- **Phase 14 (Research Identity)**: Provides deterministic identification for hypotheses and experiments (`identity_hash`).
- **Phase 28/29**: Evaluates robustness, parameter stability, and provides evolution proposals.

## 2. Identified Data and Capabilities
Existing authoritative data to reuse:
- **Evidence Links**: `SUPPORTS` and `CONTRADICTS` are already natively mapped in `EvidenceEdge`.
- **Gaps**: `EVIDENCE_GAP` nodes in the Evidence Graph.
- **Identities**: `identity_hash` string maps to hypotheses across runs.
- **Timestamps**: Strict `as_of` pattern is implemented in Graph, Planner, and Memory systems.

## 3. Minimal Additions Proposed
I will create `app/research/synthesis/`:
- `models.py`: Definitions for `KnowledgeSynthesis` and `ResearchHypothesis` following strict status mappings (`TESTABLE`, `INSUFFICIENT_EVIDENCE`, etc.).
- `repository.py`: SQLite persistence for syntheses and hypotheses, reusing the shared DB pattern.
- `synthesizer.py`: `ResearchKnowledgeSynthesizer` uses `GraphQueries` to aggregate support/contradiction edges for a given identity, assigning a `KnowledgeState`.
- `hypothesis.py`: `HypothesisGenerator` generates testable hypotheses from `KnowledgeSynthesis` and gaps. It will explicitly enforce falsifiability constraints.

## 4. Reusing Existing Lineage
- **Traceability**: Hypotheses link back to a `Synthesis`, which links back to `EvidenceNode` IDs via `GraphQueries`. No duplicate relational system will be built.
- **Decision Flow**: Hypotheses validate and translate into `ResearchQuestionCandidate` items for Phase 32.

## 5. Security & Safety
- **PAPER/RESEARCH ONLY**: Generates text and data objects. Cannot mutate parameters or issue trades.
- **AI Constraints**: LLMs will NOT be allowed to hallucinate data. The synthesizer aggregates structural evidence.
- **As_Of Boundaries**: Strict enforcement of `as_of` parameters in all queries to ensure no look-ahead.
