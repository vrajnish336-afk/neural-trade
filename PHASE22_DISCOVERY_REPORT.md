# PHASE 22 DISCOVERY REPORT: LONGITUDINAL RESEARCH CANDIDATE TRACKING

## 1. Classification of Existing Components

- **Candidate Identity (`research_identity_hash`)**: EXISTS. We will reuse this as the canonical identifier. No duplicate identity system will be created.
- **Candidate Snapshot (`ResearchCandidateSnapshot`)**: EXISTS from Phase 21. It aggregates memory, decision, track record, conflicts, opportunities, and computes Priority and Score.
- **Event Storage**: EXISTS (mostly).
  - `research_conclusions` has `created_at`.
  - `paper_health_history` has `created_at`.
  - `paper_observations` has `created_at` and `observation_end`.
  - `research_opportunities` has `created_at`.
  - `research_conflicts` does NOT have a timestamp in SQLite. (EXTEND required: we may need to add `created_at` to conflicts, or derive it from the experiments involved).
- **Chronological Ordering**: EXISTS. We can UNION or independently fetch events from these tables, order by timestamp, and iterate through them.
- **State Transitions (`StateTransition`)**: NEW. We need a model to capture `Previous Snapshot -> Event -> New Snapshot`.
- **LongitudinalTracker (`LongitudinalCandidateTracker`)**: NEW. A read-only service that compiles the timeline of snapshots by re-evaluating `build_snapshot` incrementally as events occur, or by playing back events.
- **As-Of View**: NEW. The tracker will support an `as_of` barrier to prevent future data leakage.

## 2. Reusing Phase 21 Models
We will extend `ResearchPortfolioService.build_snapshot` to support an `as_of` parameter.
By modifying the SQLite queries inside `build_snapshot` to include `AND created_at <= ?` (or equivalent for each table), we can generate a perfectly accurate, deterministic `ResearchCandidateSnapshot` for any historical second.

To build the timeline, we simply:
1. Extract all meaningful timestamps (events) for an identity_hash before `as_of`.
2. Deduplicate and sort them chronologically.
3. For each timestamp, compute `build_snapshot(identity_hash, as_of=timestamp)`.
4. Compare with the previous snapshot. If Priority, Health, Decision, or Forward Obs Count changed, record a `StateTransition`.

## 3. Explaining Transitions (No Fake Causality)
By diffing the `ResearchCandidateSnapshot` at `T-1` and `T`, we can generate deterministic explanations:
- If `Health` changed from `HEALTHY` to `WATCH`, we output: "Health state transitioned to WATCH. Associated with latest forward observation."
- If `Priority` changed from `HIGH` to `MEDIUM`, we look at `snapshot.priority_reasons` to see exactly what rule triggered it.

## 4. Security & Isolation
- **AI Isolation**: The chronological reconstruction and diffing will be 100% Python/SQLite.
- **Future-Data Barrier**: Enforced directly in SQL (`<= as_of`).
- **Live Trading**: Remains disabled. Tracking is for research evidence analysis only.

## 5. Next Steps for Implementation
1. Add `created_at` to `research_conflicts` (via migration or `ALTER TABLE` in `init_db`) so we can historically track conflict emergence.
2. Extend `ResearchPortfolioService.build_snapshot` with an `as_of: datetime` parameter.
3. Implement `app.research.longitudinal_models.py` for `StateTransition` and `CandidateTimeline`.
4. Implement `app.research.longitudinal_service.py` (`LongitudinalCandidateTracker`).
5. Update `cli.py` to add `research-history`.
6. Update `app/dashboard/components/research.py` to add the timeline UI.
7. Write `tests/test_ai_longitudinal.py` including the future-data corruption test.
