# PHASE REFACTOR RECOMMENDATIONS

Based on the actual repository dependency graph, most proposed destructive consolidations are inherently unsafe and would break the downstream aggregation architecture. 

| Phase | System | Original Assumption | Final Recommendation | Justification |
|-------|--------|---------------------|----------------------|---------------|
| 1-16 | Core Backtesting | KEEP | **DO_NOT_TOUCH** | Foundational bedrock. |
| 17 | Knowledge Models | DEPRECATE | **DO_NOT_TOUCH** | Directly imported and required by Phase 20 (Paper Monitor). Deleting breaks paper-trading event emissions. |
| 18-22 | Paper/Portfolio | KEEP | **DO_NOT_TOUCH** | Foundational for out-of-sample tracking. |
| 23 | Lessons Engine | MERGE | **DO_NOT_TOUCH** | Tightly coupled to Phase 26 (Copilot), CLI, and Phase 29 (Evolution Engine). Distinct UX lifecycle from Phase 51. |
| 24-27 | Ext. Intelligence | KEEP | **DO_NOT_TOUCH** | Standalone contextual systems. |
| 28 | Experiment Intel. | MERGE | **DO_NOT_TOUCH** | Required by Phase 29 (Evolution Engine) to parse backtest metrics. Distinct from abstract Phase 31 DAG nodes. |
| 29-30 | Orchestrator | KEEP | **DO_NOT_TOUCH** | Central automation hub. |
| 31 | Evidence Graph | KEEP | **DO_NOT_TOUCH** | The core deterministic SQLite DAG. |
| 32 | Planner | KEEP | **DO_NOT_TOUCH** | The singular human-approval queue. Consumed by Phase 53. |
| 33 | Synthesis | DEPRECATE/MERGE | **DO_NOT_TOUCH** | Phase 51 physically imports Phase 33's `SynthesisRepository` to build Canonical Knowledge. Deleting Phase 33 deletes the DB records Phase 51 relies on. |
| 34-35 | Falsify/Replicate | KEEP | **DO_NOT_TOUCH** | Unique statistical mechanisms. |
| 36 | Decay/Drift | MERGE into 50 | **REMOVE_SAFE (Logically)** | Physically already merged. Both exist natively inside the `app/research/revalidation/` directory. No action required. |
| 37 | Consensus | MERGE | **DO_NOT_TOUCH** | Phase 51 and Phase 38 (Causality) directly import `app.research.consensus.normalizer`. Distinct from Phase 45 Meta-Analysis. |
| 38-44 | Multi-Domain | KEEP | **DO_NOT_TOUCH** | Specialized portfolio/causal math. |
| 45 | Meta-Analysis | EXTEND | **DO_NOT_TOUCH** | Specialized P-hacking tracker. Distinct from generic normalization. |
| 46 | Governance | KEEP | **DO_NOT_TOUCH** | Required by Phase 53 for audit trails. |
| 47-49 | Reproduction | KEEP | **DO_NOT_TOUCH** | Verification boundaries. |
| 50 | Revalidation | EXTEND | **DO_NOT_TOUCH** | The single authority for state downgrades. |
| 51 | Canonical Knowledge | EXTEND | **DO_NOT_TOUCH** | Aggregation layer strictly dependent on Phases 33, 37, 50. |
| 52 | Knowledge Graph | KEEP | **DO_NOT_TOUCH** | Thin graph wrapper dependent on Phase 31. |
| 53 | Reasoning | EXTEND | **DO_NOT_TOUCH** | The final orchestration logic bridging Phase 51, 52, and 32. |

**CONCLUSION**: The system exhibits extreme downstream coupling. The later phases (51, 52, 53) are **orchestrators** that sit on top of the earlier phases (17, 33, 37, 50). Deleting the early phases to "consolidate" them into the later phases is akin to deleting a database to consolidate it into the frontend UI. The architecture is correctly layered as-is.
