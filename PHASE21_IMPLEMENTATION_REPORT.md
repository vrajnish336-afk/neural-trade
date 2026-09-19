# PHASE 21 IMPLEMENTATION REPORT: RESEARCH CANDIDATE PORTFOLIO & EVIDENCE-BASED COMPARISON

## 1. Exact Test Results
- **Baseline Test Count**: 201 tests (Phase 20 conclusion)
- **Final Test Count**: 206 tests (Phase 21 completion)
- **Phase 21 Focused Tests**: 5 tests added (`test_build_snapshot`, `test_missing_lineage_priority`, `test_degraded_priority`, `test_get_portfolio_sorting`, `test_compare_candidates_comparability`), all passing.
- **Full Pytest Result**: 206 passed, 0 failed, 0 skipped.
- **Compile Result**: `compileall` completed cleanly with 0 errors.
- **Security Scans**: Null-byte scan clean. Secret scan found exactly one known dummy string (`SUPER_SECRET_API_KEY_123`) inside `tests/unit/test_logging.py`.
- **Local Code Review**: Validated architecture, decoupling from live-trading, immutable boundaries, and evidence aggregation logic.

## 2. Discovery & Existing Components Reused
During discovery, it was confirmed that Phase 14-20 had already laid a phenomenal groundwork for multi-strategy lineage tracking. The `research_identity_hash` uniquely bounds a strategy, its rules, and dataset origin.
Phase 21 does not create a new data structure to store performance. It actively queries `ResearchMemory`, `ResearchConclusions`, `PaperTrackRecords`, `ResearchConflicts`, and `ResearchOpportunities` to derive an on-the-fly, read-only `ResearchCandidateSnapshot`.
The existing Phase 8 `CrossExperimentComparator` was intentionally left untouched, as it served 1-to-1 historical experiment comparisons. Phase 21 implemented `CandidateComparisonMatrix` in `portfolio_models.py` strictly for aggregating these higher-order Candidate profiles.

## 3. Architecture & Immutability
- **`ResearchPortfolioService`**: The core component acting as an aggregator.
- **`ResearchCandidateSnapshot`**: The aggregated view.
- **`ResearchPriority`**: An enum ranking candidates strictly based on their need for *Research Attention* (e.g. `VERY_HIGH` if Degraded or Conflicting, `HIGH` if missing forward validation, `MEDIUM` if completely healthy and supported).
- **Immutability Check**: The Portfolio Service executes read-only SQL joins to fetch data across the pipeline. It makes no updates, guarantees no cherry-picking, and actively penalizes missing lineage.
- **Dashboard & CLI Integrations**: The `research-candidates` and `research-compare` CLI modules were appended, and a dedicated `RESEARCH CANDIDATE PORTFOLIO` tab was woven into the main Streamlit dashboard.

## 4. Scientific Integrity Audit Responses
1. **Can PnL alone determine candidate priority?** No. Sorting is conducted via `ResearchPriority` first, and then total `ResearchEvidenceScore`. PnL is excluded from the ranking calculation entirely.
2. **Can future results rewrite previous comparisons?** No. Comparisons are executed on-the-fly based on the immutable underlying records. Old state logs remain untouched.
3. **Can poor candidates be silently excluded?** No. The portfolio queries all active identities in memory and displays them. Poor candidates are surfaced with `LOW` or `BLOCKED` priority and penalized evidence scores.
4. **Can favorable periods be cherry-picked?** No. The service relies on `PaperTrackRecordService` which enforces chronological rigidity.
5. **Can forward evidence be confused with historical evidence?** No. The `ResearchEvidenceScore` splits scoring into `historical_evidence_score` and `forward_evidence_score`.
6. **Can missing data receive a positive score?** No. Missing lineage triggers a severe penalty and enforces `BLOCKED` priority.
7. **Can AI override deterministic evidence?** No. The Portfolio Service is strictly pythonic and executes independently of LLMs.
8. **Can comparison modify strategy parameters?** No. Parameter modification is architecturally impossible here; it acts purely as a read-oriented view.
9. **Can comparison automatically select a trading candidate?** No. The output is a *Research Priority* queue, not a trading selection mechanism.
10. **Can comparison trigger unlimited research jobs?** No. It limits queries (default 50) and performs zero mutations.
11. **Can comparison enable live trading?** No. Absolute boundary checks (`config.PAPER_TRADING`, `config.LIVE_TRADING`) are enforced via `ExecutionSafetyGate`.

## 5. Files Changed
**Created**:
- `app/research/portfolio_models.py`
- `app/research/portfolio_service.py`
- `app/cli/commands/portfolio.py`
- `tests/test_ai_portfolio.py`
- `PHASE21_DISCOVERY_REPORT.md`
- `PHASE21_IMPLEMENTATION_REPORT.md`

**Modified**:
- `app/cli/main.py` (Registered `portfolio` commands).
- `app/dashboard/components/research.py` (Added Phase 21 visualization tab and logic).

## 6. Business Value & Income Goal Alignment
**HOW PHASE 21 MOVES THE PROJECT TOWARD THE LONG-TERM INCOME GOAL:**
Phase 21 prevents the most common quant trap: selecting a strategy based entirely on backtest profitability and abandoning all others. By providing a multi-dimensional portfolio that grades candidates on Health, Forward Consistency, Reproducibility, and Unresolved Conflicts, the researcher is explicitly guided toward the most *statistically sound* candidate, regardless of its flashy PnL. This creates a scalable asset queue where future, validated candidates naturally bubble to the top through proven resilience rather than curve-fitting.

## EXACT FINAL VERDICT
**PAPER / RESEARCH ONLY**
**LIVE TRADING DISABLED**

**PASS — RESEARCH CANDIDATE PORTFOLIO & EVIDENCE-BASED COMPARISON READY**
