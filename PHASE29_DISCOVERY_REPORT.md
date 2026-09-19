# PHASE 29 DISCOVERY REPORT

## 1. Existing Architecture
- **Phase 14 Research Opportunity**: Existing model in `app/research/opportunity_models.py` tracking opportunities.
- **Phase 23 Evolution Service**: Existing `EvolutionService` with `ParameterProposal` in `app/learning`. It validates types and bounds, and delegates to Phase 18 Forward Validation.
- **Phase 27 Sandbox**: Creates `ResearchSandboxExperiment`.
- **Phase 28 Experiment Intelligence**: `ExperimentComparisonService` generating `ExperimentComparison`.

## 2. Phase 29 Requirements
Phase 29 requires bridging these systems into a deterministic pipeline:
1. `ResearchGapDetector`: Analyze existing experiments to find missing validation or missing regimes.
2. `ControlledEvolutionEngine`: Translates gaps + lessons into a `ResearchEvolutionProposal` (replacing or extending `ParameterProposal`).
3. **Sandbox Integration**: The `ResearchEvolutionProposal` must require explicit human approval (state machine `DRAFT` -> `APPROVED_FOR_RESEARCH`). Once approved, it executes as a `ResearchSandboxExperiment` (Phase 27) instead of directly injecting into Forward Validation (to ensure safety gating).
4. **Comparison Loop**: After Sandbox execution, the new experiment is compared against the baseline using Phase 28's `ExperimentComparisonService`. This results in a final `ResearchAnswer` (SUPPORTED / INCONCLUSIVE / NOT_SUPPORTED).

## 3. Storage
- `evolution_proposals` table to store `ResearchEvolutionProposal`.

## 4. Safety Gates
- AI does not mutate strategy.
- Explicit human approval required before execution.
- No PnL-based ranking for proposing experiments.
