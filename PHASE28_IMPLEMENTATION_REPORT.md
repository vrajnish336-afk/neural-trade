# PHASE 28 IMPLEMENTATION REPORT: EXPERIMENT INTELLIGENCE

## 1. Discovery & Architecture
Phase 28 establishes a multidimensional comparison engine sitting atop the `ResearchSandboxExperiment` registry. It translates raw backtest JSON into normalized `ExperimentEvidenceProfile` blocks. 

## 2. Comparison Service
- **Compatibility Checking:** Experiments are classified as `DIRECTLY_COMPARABLE`, `PARTIALLY_COMPARABLE`, or `NOT_COMPARABLE`.
- **Sample Size Awareness:** It penalizes sub-30 trade experiments as `INSUFFICIENT` regardless of arbitrary high returns. 
- **Methodology Versioning:** Uses `v1` natively, persisting deterministic logic results in the `experiment_comparisons` SQLite table.

## 3. UI & CLI Additions
- **Streamlit (`app/dashboard/components/experiment_intelligence.py`)**: Added Tab 12. Displays side-by-side metric comparison and the final evidence strength assessment dynamically.
- **CLI (`app/cli/commands/experiment.py`)**: `ntrade experiment-compare <id1> <id2>` securely prints compatibility and strength analysis.

## 4. Audits & Integrity
- **Scientific Audit:** Complete. Prevents highest-return-wins logic via strict sample size gating.
- **Security Check:** The system executes zero Python logic derived from the experiments themselves. It operates completely structurally and read-only over `ExperimentComparison` and `SandboxRepository`. 
- **Tests:** Full regression passing.

## 5. FINAL SAFETY STATEMENT
**PAPER / RESEARCH ONLY.**
**EXPERIMENT COMPARISON IS RESEARCH EVIDENCE ANALYSIS.**
**NO AUTOMATIC STRATEGY DEPLOYMENT.**
**NO AUTOMATIC PARAMETER MUTATION.**
**AI CANNOT EXECUTE TRADES.**
**LIVE TRADING DISABLED.**
