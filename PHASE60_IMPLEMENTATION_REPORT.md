# PHASE 60 — CONTROLLED SELF-LEARNING & EVOLUTION ENGINE

## 1. STATUS
**PASS**

## 2. GSD Implementation Summary
- **Discovery**: Examined the existing `LearningRepository`, `LessonEngine`, and `PaperRepository`. Discovered that Phase 29 already implemented research-based sandbox evolution. However, Phase 60 specifically requires evolution on *live paper trading* configurations. Thus, we reused the mental model but introduced dedicated models and engines specifically tied to paper portfolio closed trades, avoiding side-effects with sandbox infrastructure.
- **Plan**: Extract `PostMortemObservation` directly from `paper_closed_positions`. Generate `PaperResearchLesson`s deterministically by grouping the observations. Synthesize `EvolutionProposal`s that suggest updates to specific safe configuration parameters (like `MIN_SIGNAL_SCORE`). Introduce a dashboard UI for explicit human review and application.
- **Implement**: 
    - `PaperEvolutionRepository` for SQLite persistence of paper lessons and proposals.
    - `PaperEvolutionEngine` comprising `PostMortemAnalyzer`, `LessonExtractor`, and `EvolutionProposalEngine`.
    - Dashboard tab `18. PHASE 60 PAPER EVOLUTION` providing complete visibility into lessons, pending proposals, and explicit human approval buttons.
- **Test**: Added focused tests proving lesson constraints, insufficient samples, runaway loop prevention, human approval requirement, execution bounds, and stale parameter drift rejection.
- **Audit**: Analyzed SQLite connections (fixed a teardown connection leak), validated strictly against unbounded source code execution (the configuration updater uses simple in-memory `setattr(config, ...)`), and preserved `RiskEngine` authority.

## 3. Ralph Loop Iteration Count
- Iterations: 2 (First pass caught SQLite connection leakage in tests; second pass resolved connection lifecycle).

## 4. CodeRabbit-style Findings & Fixes
- **Finding (Data Integrity)**: Original `paper_closed_positions` does not natively store the `strategy` and `regime` fields used at decision time.
  - **Fix**: To avoid fabricating evidence or hallucinating context, `PostMortemAnalyzer` strictly maps these to `"UNKNOWN"` when deriving from the raw ledger, ensuring we only evaluate hard statistical performance (PnL, win rate) rather than assuming conditions.
- **Finding (Resource Leak)**: `PaperEvolutionRepository` was committing transactions but failing to close connections in some methods.
  - **Fix**: Standardized connection lifecycle using `try/finally` or explicit `conn.close()` inside the DB layer.
- **Finding (Safety Boundary)**: An AI could potentially modify critical risk limit constants.
  - **Fix**: Hardcoded a `SAFE_PARAMETERS` allowlist containing only benign strategic thresholds (e.g., `MIN_SIGNAL_SCORE`).

## 5. Files Changed
- `app/learning/paper_evolution_models.py` (New): Data schema for paper-based observations, lessons, and proposals.
- `app/learning/paper_evolution_repository.py` (New): Idempotent database handling.
- `app/learning/paper_evolution_engine.py` (New): Core extraction and proposal generation logic with runaway loop guards.
- `app/dashboard/components/phase60_evolution.py` (New): UI for Human-in-the-Loop review and application.
- `app/dashboard/app.py`: Registered the new dashboard tab.
- `tests/unit/test_phase60_evolution.py` (New): 8 focused Phase 60 test cases.

## 6. Existing Lessons Bank
The existing `research_lessons` (Phase 23/29) was designed for Sandbox validations which have different metadata. Phase 60 uses a parallel table `phase60_lessons` to cleanly isolate live paper trading lessons from offline sandbox backtest lessons, while preserving the exact same architectural principles and determinism.

## 7. Post-Mortem Architecture
The `PostMortemAnalyzer` is deterministic and pure. It queries `paper_closed_positions` directly via `PaperRepository`, calculating exact holding durations, win/loss binaries, and realized PnL. It refuses to utilize look-ahead data or fabricate unavailable strategy metadata.

## 8. Lesson Schema
```python
class PaperResearchLesson:
    lesson_id: str
    source_trade_ids: List[str]
    strategy: str
    regime: str
    observation: str
    sample_count: int
    wins: int
    losses: int
    observed_pnl: float
    confidence_status: LessonState
    created_at: datetime
    data_window_start: datetime
    data_window_end: datetime
```

## 9. Evidence / Anti-Overfitting Gates
- Minimum sample size enforced: Lessons with `< 5` observations are marked `INSUFFICIENT_EVIDENCE`.
- Win rate bounds: Lessons only achieve `VALIDATED` status if there is a mathematically clear skew (win rate > 60% with +PnL, or < 40% with -PnL). Everything else is `CONTRADICTED`.
- Parameter drift protection: If `config.MIN_SIGNAL_SCORE` changes between the time a proposal is generated and the human approves it, the proposal is marked `EXPIRED` and rejected.

## 10. Evolution Proposal Schema
Contains full traceability: `proposal_id, lesson_ids, evidence_ids, affected_strategy, affected_parameter, current_value, proposed_value, delta, reason, evidence_summary, sample_size, validation_status, status`.

## 11. Human Approval Workflow
- Proposals enter `REVIEW_REQUIRED`.
- Dashboard exposes an explicit `APPROVE & APPLY` or `REJECT` button.
- Without a manual UI interaction, proposals lie dormant indefinitely.
- AI has no mechanism to interact with the Dashboard UI components.

## 12. Parameter Allowlist
- `MIN_SIGNAL_SCORE`
- `NEWS_LOOKBACK_HOURS`
- `ANOMALY_ZSCORE_THRESHOLD`
- `MIN_ARTICLE_RELEVANCE`

## 13. Explicitly Forbidden Parameters
- `PAPER_TRADING`, `LIVE_TRADING`
- Core Risk settings: `MAX_POSITION_SIZE`, `RISK_PER_TRADE`, `DAILY_LOSS_LIMIT`, `MAX_POSITIONS`, etc.

## 14. Application/Rollback Behavior
If approved, `setattr(config, parameter, proposed_value)` applies the adjustment in-memory immediately. The UI provides a `ROLLBACK` button to instantly revert to `current_value` if adverse effects are noticed.

## 15. Runaway Loop Protections
- Duplicate lesson filtering via identical sample count detection.
- A single parameter can only have one active/pending proposal at a time.
- State transitions are one-way.
- AI cannot trigger the configuration updater.

## 16. AI Boundary
Phase 60 operates completely via deterministic heuristics for performance measurement and proposal mapping. The system does not utilize an LLM to formulate the configuration overrides; they are bounded by mathematical deltas to guarantee safety.

## 17. Dashboard Changes
Introduced "18. PHASE 60 PAPER EVOLUTION", preserving existing "13. SELF-EVOLUTION LAB" layout logic but exposing actual paper portfolio analysis.

## 18. Exact Focused Test Counts
- 8 Passed
- 0 Failed
- 0 Skipped

## 19. Full Regression Counts
- Full regression passed: 461
- Full regression failed: 0
- Warning count: ~650 (Standard deprecation warnings)

## 20. Collection Errors & Known Failures
- `tests/test_kronos_integration.py` — Explicitly excluded (WinError 4551).
- `test_ai_forecasting.py` — Behaved stably during this run.

## 21. Security/Accounting/Chronology Audit
- **Chronology**: `data_window_end` strictly binds the lesson to historical timestamps.
- **Security**: No `eval()` or code modification executed. Config changes are bounded `setattr` calls mapped against an allowlist.
- **Accounting**: Realized PnL is exclusively derived from immutable `paper_closed_positions` ledger entries.

## 22. Confirmations
`PAPER_TRADING=true`
`LIVE_TRADING=false`

## 23. RiskEngine Authority
Because parameter adjustments are bounded solely to signal thresholds (e.g. `MIN_SIGNAL_SCORE`), the `RiskEngine` rules (including Phase 59 drawdown halters) remain universally untouched and authoritative over trade execution.

## 24. Limitations
- `paper_closed_positions` does not store `strategy` and `regime`. Thus, `PostMortemAnalyzer` operates broadly rather than surgically on specific strategy signals.
- Config updates are in-memory (via `setattr(config, ...)`). Restarting the Python process reverts them. True permanence requires `.env` modification, which is inherently dangerous and was avoided to strictly comply with "do not modify python source code/files autonomously".

## 25. Recommended Next Phase
- Phase 61: Inject `strategy` and `regime` directly into `paper_orders` and `paper_closed_positions` schemas to dramatically increase the granularity of lessons extracted from live paper trades.
