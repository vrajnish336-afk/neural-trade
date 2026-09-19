# Phase 13 Discovery Report

## 1. Baseline Test Metrics
- **BASELINE_TEST_COUNT**: 163
- **BASELINE_PASS**: 163
- **BASELINE_FAIL**: 0
- **BASELINE_SKIP**: 0

## 2. Current Architecture & Reusable Components
- **Phase 12 AI Agent**: Parses news into an `AIAnalysisResult` containing fields like `evidence_type`, `research_hypothesis`, and `affected_symbols`. This is persisted in the `ai_research_analysis` table.
- **BacktestEngine (`app/backtesting/engine.py`)**: The core deterministic simulation engine. Takes chronological `MarketBar` lists and evaluates strategies without look-ahead bias.
- **Evidence Evaluator (`app/research/evidence.py`)**: Handles robustness, sample size constraints, and OOS checks, yielding an `EvidenceSummary`.
- **Telemetry (`app/diagnostics/telemetry.py`)**: Records rejection reasons and pipeline stages.

## 3. Proposed Integration Point (The Research Loop)
The Phase 13 integration orchestrates a flow from unstructured text to deterministic research without allowing arbitrary code execution.
1. **Query**: Find pending `AIAnalysisResult`s with `evidence_type = "RESEARCH_HYPOTHESIS"`.
2. **Validate**: Check constraints (e.g., are the symbols supported in our dataset? Is the hypothesis well-formed?).
3. **Map**: Translate the hypothesis into deterministic parameters. (e.g., if hypothesis is about volatility, set up a generic mean-reversion or breakout strategy run).
4. **Execute**: Run `BacktestEngine` with strictly historical data.
5. **Evaluate**: Pass results to `ResearchEvidenceEvaluator`.
6. **Persist**: Save the `AIResearchRequest` and the final `EvidenceSummary`.

## 4. Safety Boundary & Mapping
- The AI cannot generate code. We will map its `research_hypothesis` text to predefined safe strategies via an explicit deterministic `HypothesisMapper`.
- If a hypothesis requests an unknown strategy or unsupported symbol, the status is set to `INSUFFICIENT_RESEARCH_SPECIFICATION` and execution halts.
- Costs (slippage/commission) are handled exclusively by the `BacktestEngine` and its `CostConfig`.

## 5. Persistence
We will introduce an `ai_research_requests` table to track the orchestration lifecycle.
Schema will include:
- `request_id`
- `analysis_id` (FK to ai_research_analysis)
- `status`
- `mapped_strategy`
- `dataset_identity`
- `evidence_conclusion`

## 6. Risks & Performance
- **Risk**: Double-counting costs if we misinterpret PnL. (Mitigation: Use `BacktestEngine`'s native metrics directly).
- **Risk**: Look-ahead bias. (Mitigation: BacktestEngine inherently prevents it by stepping sequentially).
- **Performance**: We will only process a bounded batch of hypotheses at a time via the CLI to avoid an infinite loop of backtesting.
