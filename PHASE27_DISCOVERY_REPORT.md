# PHASE 27 DISCOVERY REPORT

## 1. Backtesting & Strategies
- `app.strategies.base.Strategy` is a protocol requiring `name`, `generate_signal(historical_bars)`, and `get_parameters()`.
- `app.backtesting.engine.BacktestEngine` runs a chronologically strict loop using `StrategyEnsemble`.
- We can wrap an AI-generated function into a dynamic `Strategy` adapter, inject it into an ensemble, and run a paper backtest.

## 2. Sandbox Requirements & Execution Limitations
- The Windows environment lacks true OS-level containers (like Docker natively without relying on Docker Desktop). Standard Python `subprocess` with restricted globals is the most feasible limited sandbox here.
- The `GSD` rules state: "If a true OS/container sandbox is unavailable... implement the strongest practical restriction... and explicitly state the isolation level."
- I will implement AST static analysis to reject dangerous imports, globals, and builtins.
- I will execute the approved script using `multiprocessing` or `subprocess` to provide memory and timeout isolation, but since it shares the host OS, it's categorized as a "LIMITED RESEARCH EXECUTION ENVIRONMENT".

## 3. Storage & AI Connection
- We will store proposals and experiment results in SQLite (`research_sandbox_experiments`, `research_code_proposals`).
- The Phase 26 Copilot (read-only) will be updated or paired with a new CLI command (`ntrade code-propose`) that can invoke the existing AI provider to *write* the code proposal, which is then serialized to disk/db without execution.

## 4. Safety Guarantees
- No modifications to project files.
- The RiskEngine firewall remains perfectly intact because the Sandbox Backtest is entirely historical/paper.
