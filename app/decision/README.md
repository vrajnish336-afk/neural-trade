# Trader Decision Loop Integration

The `app.decision` package unifies the existing intelligence, forecasting, strategy, and risk components into a deterministic `DecisionOrchestrator`.

## Paper Execution Blocker
As of Phase 55, the existing "paper execution" API (located in `app.research.track_record_service.py`) relies exclusively on aggregating `ForwardValidationRun` objects (which are effectively historical backtest slices). There is currently **no live streaming paper execution API** or simulated broker service that accepts single `TraderDecision` orders in real-time. 

Rather than creating a fake execution pathway that bypasses the existing system, the `TraderDecision` model exposes a `paper_execution_eligible` flag that accurately indicates whether the decision has passed the absolute risk veto. A true real-time paper execution broker must be built and integrated here before these decisions can be autonomously logged into a live paper track record.
