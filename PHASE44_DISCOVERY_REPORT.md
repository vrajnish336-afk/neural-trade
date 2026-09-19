# PHASE 44 DISCOVERY REPORT: ADAPTIVE PORTFOLIO STRESS DISCOVERY & FAILURE INTELLIGENCE

## 1. Existing Infrastructure Analysis
- **Phase 43 (Portfolio Stress)**: Generates `PortfolioStressResult` identifying structural adversarial breaks (`PortfolioFailureAssessment` like `CORRELATED_FAILURE`, `COST_FRAGILITY`).
- **Phase 32 (Planner)**: Exposes logic for scoring via `ResearchPriorityBreakdown`, `ResearchDecisionState`, and information-value heuristics without automatically mutating the portfolio.
- **Phase 34 (Hypotheses)**: Standardizes `Hypothesis` mapping which requires a testable `falsification_condition`.

## 2. Identified Research Gaps
- The system flags a `PortfolioFailureAssessment` but does not translate this observation into an actionable scientific `PortfolioResearchQuestion` or `Hypothesis`.
- We need a layer that identifies *when* an adversarial observation warrants further dedicated experimentation, whilst applying deterministic checks for evidence saturation (don't propose the same research twice) and staleness (has this temporal window passed?).

## 3. Integration Strategy
- **Package Creation**: We will create `app/research/portfolio_discovery/` acting as the bridge between Portfolio Stress and the Global Planner.
- **Failure Extraction**: `signals.py` will deterministically map Phase 43 assessments (e.g., `REGIME_FRAGILITY`) to explicit gaps (e.g., `REGIME_GENERALIZATION_GAP`).
- **Hypothesis Generation**: The engine will output `PortfolioResearchQuestion` equipped with falsification limits and replication requirements.
- **Priority Logic**: The system will leverage Phase 32 `ResearchPriorityBreakdown`, prioritizing structural overlaps and cost sensitivity without conflating `high priority` with `high allocation probability`.
- **Safety**: Human approval remains mandatory. All items spawn as `REVIEW_REQUIRED`.

## 4. Mandatory Constraints
- NO AUTOMATIC OPTIMIZER.
- Novelty check must be deterministic via `research_identity`, avoiding unpredictable LLM decision-making.
- All proposals explicitly track `sample_size_state` and refuse to treat tiny backtests as definitive proof.
