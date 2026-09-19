# PHASE 20 DISCOVERY REPORT: CONTROLLED PAPER RESEARCH MONITORING & INTELLIGENCE CYCLE

## 1. Existing Architecture & Baseline
- **Baseline Test Count**: 197 tests
- **Phase 19 `PaperTrackRecordService`**: Already handles appending `ForwardValidationRun`s chronologically, recalculating cumulative equity, evaluating strategy health (`HEALTHY`, `WATCH`, `DEGRADED`, `CRITICAL`), and generating a Phase 14 `ResearchOpportunity` upon degradation.
- **Phase 18 `ForwardValidationService`**: Persists `ForwardValidationRun` objects in `forward_validation_runs`.
- **Phase 17 `KnowledgeService`**: Exists to record decisions and evidence gaps.
- **Phase 16 `DecisionEngine`**: Resolves conflicts and arrives at research conclusions.
- **Phase 15 `ResearchJobOrchestrator`**: Manages bounded asynchronous jobs (`run_cycle`).

## 2. Gaps & Missing Links
- **No Continuous Discovery**: Currently, `PaperTrackRecordService.append_validation_run` is a passive method. Nothing actually scans the `forward_validation_runs` table for newly `COMPLETED` runs to ingest them.
- **No Knowledge Integration**: Phase 19 correctly emits an Opportunity on degradation, but it does NOT record a `ResearchKnowledgeChange` when health transitions.
- **Decision Engine Isolation**: The Decision Engine needs to be triggered if the monitoring cycle finds that evidence has shifted (e.g., drift).
- **No Bounded Cycle**: There is no top-level `PaperMonitoringCycle` that limits how many validations to process per run and provides idempotency at the cycle level.

## 3. Proposed Phase 20 Architecture (The Monitoring Cycle)
### Component: `PaperMonitoringService`
A deterministic, restart-safe service that executes the following loop:
1. **Discover**: Find `COMPLETED` runs in `forward_validation_runs` that do not exist in `paper_observations`.
2. **Limit**: Take only up to `max_validations_per_cycle` to ensure bounded work.
3. **Ingest**: Pass each discovered run to `PaperTrackRecordService.append_validation_run(run)`.
4. **Detect & Update**: If `PaperTrackRecordService` modified the health state, explicitly call Phase 17 to log a `ResearchKnowledgeChange` detailing the transition.
5. **Decide**: Trigger the `DecisionEngine` for the affected `identity_hash` to re-weigh the new out-of-sample experiment against historical data.
6. **Telemetry & Persist**: Return a structured `CycleResult` containing counts of validations processed, health changes, and errors.

### Cycle Result Model
```python
class MonitoringCycleResult(BaseModel):
    cycle_id: str
    status: str # COMPLETED, NO_CHANGES, PARTIAL, FAILED
    validations_discovered: int = 0
    observations_recorded: int = 0
    health_transitions: int = 0
    knowledge_updates: int = 0
    errors: int = 0
```

## 4. Safety & Immutability Guarantees
- **No Live Trading**: The entire cycle remains paper-only.
- **Idempotency**: If the cycle is run twice without new `ForwardValidationRun`s, it returns `NO_CHANGES`. It relies on the unique `validation_id` to prevent double-appending.
- **No Automatic Strategy Changes**: The system only generates `ResearchKnowledgeChange` and `ResearchOpportunity`. It does NOT mutate frozen parameters.

## 5. Required Files
- `app/research/monitoring_models.py` (for `MonitoringCycleResult`)
- `app/research/monitoring_service.py` (for the actual cycle loop)
- `app/cli/commands/monitor.py` (CLI entry point)
- `tests/test_ai_paper_monitor.py` (Focused tests)
- `PHASE20_IMPLEMENTATION_REPORT.md`
