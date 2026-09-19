# PHASE 42 DISCOVERY REPORT: ADVANCED PORTFOLIO RESEARCH & CROSS-STRATEGY ALLOCATION INTELLIGENCE

## 1. Existing Infrastructure Analysis
- **Candidate Snapshot**: Phase 21 created `ResearchCandidateSnapshot` in `app.research.portfolio_models`, which tracks forward observation counts, current health (`StrategyHealthState`), latest drift, and decision state.
- **Execution & Models**: `MarketBar` and `TradingSignal` form the basis of execution.
- **Timeframes**: Phase 41 introduced multi-timeframe boundaries and strictly enforces them. 
- **Walk Forward / Out Of Sample**: Phase 40 and 18 ensure strict out-of-sample generation and boundary locks via `ForwardValidationService` and `WalkForwardWindowBuilder`.
- **Regime Detection**: `detect_market_regime` tags bars into states like TRENDING_UP, TRENDING_DOWN, etc.

## 2. Integration Strategy
- **Package Creation**: We will create `app/research/portfolio_intelligence/` to encapsulate cross-strategy portfolio interactions while completely avoiding live routing or deployment logic.
- **Data Series construction**: The system will accept candidate identities, extract their simulated paper returns or daily tracking metrics, and align them onto a shared timeline ensuring NO SURVIVORSHIP BIAS and chronological `as_of` tracking.
- **Diversification & Correlation**: We will implement statistical modules to measure return overlap, drawdown overlap, and regime overlap without claiming causation. 
- **Cost Interaction**: Will ensure we don't assume zero slippage/commission when summing multiple high-frequency models.

## 3. Mandatory Safety Rules Enforced
- **NO AUTOMATIC OPTIMIZER**: We will explicitly build `equal_weight` or `declared_weight` configurations. We will explicitly NOT write maximizing functions (like max Sharpe solvers) because forward weights cannot be selected by backtest performance without introducing future-leakage.
- NO LIVE ALLOCATION. 
- STRICT AS_OF: The system restricts candidate availability relative to the target time constraint.

## 4. Architecture Plan
- `app/research/portfolio_intelligence/models.py` (DiversificationAssessment, PortfolioResearchSnapshot, Eligibility)
- `app/research/portfolio_intelligence/correlation.py` (Math for overlap/correlation)
- `app/research/portfolio_intelligence/portfolio.py` (Constructing series and assessing weights)
- `app/research/portfolio_intelligence/evaluator.py` (Ablation and Temporal generalisation wrapper)
- `app/research/portfolio_intelligence/service.py` (High-level research entry points)
