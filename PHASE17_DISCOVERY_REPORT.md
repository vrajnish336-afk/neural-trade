# PHASE 17 DISCOVERY REPORT: RESEARCH KNOWLEDGE CONSOLIDATION

## 1. Current Research Architecture
The current architecture spans Phases 1–16 and heavily relies on offline, deterministic processes:
1. **News/Hypothesis**: `ai_research_analysis` generates textual hypotheses.
2. **Opportunity/Memory**: `ResearchMemory` establishes a canonical `identity_hash`. `OpportunityIntelligence` scores it (Novelty, Evidence Gap, Data Availability).
3. **Orchestrator**: Creates `ResearchJob` records and triggers deterministic backtests (`ResearchExperiment`).
4. **Evidence/Decision**: `ResearchEvidenceEvaluator` parses the experiment into an `EvidenceSummary`. `ResearchDecisionEngine` groups these by `identity_hash` to generate a `ResearchConclusion` and explicitly record `ResearchConflict`s.

## 2. Existing Research Entities
- `ResearchExperiment` (raw backtest results + analytics)
- `ai_research_requests` (legacy mapping)
- `ResearchMemoryRecord` (identity mapping)
- `ResearchOpportunity` (scored potential)
- `ResearchJob` (execution state)
- `ResearchConclusion` (macro decision state)
- `ResearchConflict` (direct contradictions)
- `ResearchRelationship` (edges)

## 3. Duplicated Concepts
- Currently, "what we know" is scattered. To understand a strategy, one must query Memory, Opportunities, Jobs, Conclusions, and Conflicts separately.
- "Evidence Gaps" are conceptually used to score opportunities but are not explicitly modeled or tracked as discrete entities that require resolution.

## 4. Missing Knowledge-Layer Capabilities
- **Change Detection**: We store `ResearchConclusion`s immutably, but we don't track the *delta* (e.g., INSUFFICIENT_EVIDENCE -> MIXED_EVIDENCE).
- **Snapshot Generation**: No single API produces a unified `ResearchKnowledgeSnapshot` aggregating total experiments, gaps, conflicts, and the active decision.
- **Evidence Gaps**: No discrete `EvidenceGap` tracking.
- **Bounded Graph Traversal**: Relationships exist, but there is no safe, bounded traversal API.

## 5. Proposed Unified Architecture
We will introduce a `ResearchKnowledgeService` as a pure read/aggregation/versioning layer sitting on top of existing data. It will **not** duplicate experiment data.

## 6. Proposed Models & Tables
1. **`ResearchKnowledgeSnapshot` (Pydantic Model only)**: An ephemeral, on-demand aggregation of memory, conclusions, conflicts, and jobs.
2. **`ResearchKnowledgeChange` (Table: `research_knowledge_changes`)**: Records state transitions.
   - `change_id`, `identity_hash`, `previous_decision`, `new_decision`, `previous_confidence`, `new_confidence`, `reason`, `source_conclusion_id`, `created_at`.
3. **`EvidenceGap` (Table: `research_evidence_gaps`)**: Explicitly tracks missing requirements.
   - `gap_id`, `identity_hash`, `gap_type`, `severity`, `status`, `recommended_action`, `created_at`, `resolved_at`.

## 7. Migration & Identity Strategy
- Identity remains the Phase 14 `identity_hash` (`ResearchIdentity`).
- We will NOT modify historical tables. We will simply add the two new tracking tables (`research_knowledge_changes` and `research_evidence_gaps`).

## 8. Test Strategy
- Ensure deterministic identity is untouched.
- Test that a change from Conclusion A to Conclusion B correctly emits a `ResearchKnowledgeChange`.
- Test bounded graph traversal (e.g. `max_depth=2` stops correctly).
- Verify AI boundary (snapshot can be stringified for AI, but AI cannot execute queries).

## 9. Performance & Security Risks
- **Performance**: We will use SQL joins to build snapshots rather than pulling everything into memory.
- **Security**: No `eval`, no arbitrary SQL. Bounded graph traversal prevents OOM via cycles.

## 10. Expected File Changes
**Created**:
- `app/research/knowledge_models.py`
- `app/research/knowledge_service.py`
- `app/cli/commands/research_knowledge.py`
- `tests/test_ai_research_knowledge.py`

**Modified**:
- `app/database/schema.py` (Add new tables)
- `app/cli/main.py`
- `app/dashboard/components/research.py` (Add Knowledge Tab)
- `app/research/decision_engine.py` (To hook change detection when a new conclusion is minted)
