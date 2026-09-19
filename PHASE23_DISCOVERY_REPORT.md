# PHASE 23 DISCOVERY REPORT

## 1. Existing Architecture & Concepts
- **Historical Outcomes**: `paper_observations` contains `net_pnl`, `drawdown_pct`, `win_rate`, `profit_factor`, `trade_count`, and `regime_distribution_json`.
- **Strategy Identity**: `research_memory` links an `identity_hash` to a `mapped_strategy`.
- **Regime Information**: Stored per-observation in `regime_distribution_json`.
- **Parameter Representation**: `Strategy` implementations return a dictionary via `get_parameters()`. `ForwardValidationRun` freezes specs in `frozen_specification`.
- **Forward Validation**: Orchestrated via `ForwardValidationService.create_run(...)`.
- **AI Research Integration**: The `AiResearchAgent` handles hypothesis evaluation but MUST NOT be allowed to hallucinate data.

## 2. Reusability Assessment
- **Identity System**: `identity_hash` from `research_memory` and `ForwardValidationRun` provides exact provenance. We will reuse this.
- **Data Tables**: `paper_observations` provides the exact empirical data for Trade Analysis without needing a secondary database.
- **Safety**: `config.PAPER_TRADING` and `ExecutionSafetyGate` securely isolate the system. We will uphold this invariant in the Evolution Service.

## 3. Integration Points
- **Trade Analyzer**: Will query `paper_observations` to find patterns (e.g., performance grouped by primary regime).
- **Lesson Extraction**: AI summary of Trade Analyzer outputs, verified deterministically before being saved to a `lessons` SQLite table.
- **Ranked Bank**: New `lessons` table, ranked deterministically via (sample_size * consistency) - penalty.
- **Evolution Proposal**: Will capture baseline parameters, propose changes, validate types against `strat.get_parameters()`, and persist in an `evolution_proposals` table.
