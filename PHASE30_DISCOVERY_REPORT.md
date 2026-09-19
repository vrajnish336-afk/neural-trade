# PHASE 30 DISCOVERY REPORT

## 1. Existing Orchestration
- **Phase 15 (`ResearchJobOrchestrator`)**: Operates a state machine (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `RETRY_WAIT`) to turn raw AI hypotheses into initial `ResearchExperiment` records via standard backtests.
- **Phase 29 (`ControlledEvolutionEngine`)**: Detects gaps, proposes bounded parameter changes, requires human `REVIEW_REQUIRED` -> `APPROVED_FOR_RESEARCH`, and executes a sandbox experiment followed by an `ExperimentComparison`.

## 2. Phase 30 Requirements
Phase 30 sits *above* Phase 15 and 29. It is the "Continuous Research Autopilot".
It must loop over:
1. Trigger Gap Detection (Phase 29).
2. Generate Opportunities/Proposals.
3. Place them in an approval queue (Phase 29 `EvolutionProposalState`).
4. **STOP** and wait for human approval (State: `WAITING_FOR_RESEARCH_APPROVAL`).
5. After human approval via CLI/Streamlit, automatically resume.
6. Trigger Experiment Execution (Sandbox).
7. Trigger Validation & Comparison (Phase 28).
8. Generate Lessons (Phase 23) and Knowledge.

## 3. Architecture
- We will build `ContinuousResearchOrchestrator` in `app/research/continuous_orchestrator.py`.
- It will define a `ResearchCycle` model tracking the high-level state of a single pass of the research loop.
- It will NOT replace `ResearchJobOrchestrator` but rather orchestrate the `ControlledEvolutionEngine` (which handles the Phase 29 lifecycle) in a bounded loop.
- We will store cycles in `research_cycles` table.
- A cycle will block if a proposal requires approval, allowing UI to `ntrade research-approve` and then the next tick of the orchestrator will resume it.

## 4. Safety Gates
- Cycle completely pauses at `WAITING_FOR_RESEARCH_APPROVAL`.
- Hard resource budget (e.g. max proposals per cycle).
- Cycle idempotency: resuming a paused cycle picks up where it left off.
