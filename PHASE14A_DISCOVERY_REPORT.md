# Phase 14 Discovery Report: Research Memory & Opportunity Intelligence

## 1. Baseline Test Metrics
- **BASELINE_TEST_COUNT**: 171
- **BASELINE_PASS**: 171
- **BASELINE_FAIL**: 0
- **BASELINE_SKIP**: 0

## 2. Current Architecture & Integration Points
The current pipeline securely generates deterministic backtests from AI natural language hypotheses (`ai_research_requests` table, `ResearchLoopOrchestrator`).
Phase 14 sits directly between `AIAnalysisResult` generation and `AIResearchRequest` creation. It acts as a filter and prioritize.

- **News**: Stored in `news_articles`.
- **AI Analysis**: Stored in `ai_research_analysis`.
- **Integration Layer (Phase 14)**: Will intercept unmapped AI Analysis results, deduplicate them using `ResearchMemory`, score their research value using `OpportunityIntelligence`, and store them as `research_opportunities`.
- **Execution Loop**: The Phase 13 `ResearchLoopOrchestrator` will be modified (or augmented) to only execute explicit `research_opportunities` rather than blindly processing all hypotheses. *Wait, the prompt says "If an action triggers Phase 13 research, require explicit invocation." The CLI `research-loop` already requires explicit invocation. We will ensure the orchestrator sources from opportunities.*

## 3. Architecture Design

### A. Research Memory & Identity
- **`ResearchIdentity`**: A SHA-256 hash derived from:
  - `lower(strip(mapped_strategy))`
  - `sorted(affected_symbols)`
  - `lower(strip(hypothesis_text))` (or a normalized subset)
- **`ResearchMemoryRepository`**: Provides read-oriented lookups:
  - `find_by_identity(identity_hash)`
  - `get_previous_conclusion(identity_hash)`

### B. Duplicate Detection
- Exact match on `identity_hash` yields `status = DUPLICATE`.
- If it's a duplicate, we do NOT throw it away, but we link it to the existing `research_memory` record.

### C. Opportunity Scoring
Scoring evaluates the *usefulness* of research, strictly explicitly separated from "expected PnL".
Formula components (0.0 to 1.0):
- **Novelty**: High if `identity_hash` is unseen. Low if seen.
- **Evidence Gap**: High if previous conclusion was `INSUFFICIENT_DATA` or `WEAK`. Low if `VERIFIED`.
- **Data Availability**: Heuristic based on whether the symbols exist in our local CSVs.

### D. Models
- `ResearchOpportunity` (Pydantic model)
- Database tables to add to `SCHEMA_SQL`:
  - `research_memory`: Tracks the canonical identity of a research vector and links to the latest experiment/evidence.
  - `research_opportunities`: Tracks proposed research ideas scored by the intelligence layer.

### E. CLI & UI
- **CLI**: `python cli.py research-memory`, `python cli.py opportunities`
- **Dashboard**: Extend `app/dashboard/components/research.py` to display the Opportunity Backlog.

## 4. Security & Integrity Check
- AI has NO agency in executing these opportunities. It simply provides the text that gets scored.
- Opportunities DO NOT trigger orders.
- Scoring explicitly avoids PnL to prevent data snooping and optimization.

Next steps: Implement models, memory layer, scoring logic, and integrate with CLI/Dashboard.
