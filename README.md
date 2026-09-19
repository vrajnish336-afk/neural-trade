# AI Trading Bot

This is a serious AI-assisted trading research and paper-trading platform. 

## Current Phase: Phase 4 (Ensemble, Multi-Timeframe & Risk Integration)
The project currently possesses a fully integrated risk engine, multi-timeframe resampling, regime detection, and a strategy ensemble framework.

### Current Capabilities
- **Risk Engine Integration**: Trades are rigorously evaluated for portfolio exposure limits, absolute position size constraints, daily loss limits, and a loss-streak cooldown system. The engine operates dynamically based on precise Stop Loss distances.
- **Multi-Timeframe Context**: Deterministic historical resampling allows safe context without look-ahead bias.
- **Market Regime Detection**: Classifies the market into Trending Up, Trending Down, Range Bound, or High Volatility based on momentum and ATR.
- **Strategy Ensemble**: Combines outputs from baseline strategies and deterministically scores them based on regime alignment and strategy consensus. The ensemble can resolve conflicts and veto trades that mismatch the prevailing regime.
- **Trade Explanation Metadata**: Emits comprehensive scoring, regime, and strategic reasoning directly into the executed `BacktestTrade` logs.
- **Technical Indicators**: Deterministic implementations of SMA, EMA, RSI, ATR, ROC, and Volatility using pandas.
- **Strategies**: Baseline strategies included for research (Trend Following, Breakout, Mean Reversion).
- **Backtesting Engine**: Event-driven backtester simulating chronological progression to absolutely prevent look-ahead bias.
- **Configuration**: Safe environment-based configuration for risk thresholds (daily loss limit, streak cooldown).

### Why the System Might Say "NO TRADE"
The trading engine is built defensively. A trade will be rejected (or wait) if:
1. **Regime Veto**: The generated signal goes strongly against the current market regime (e.g. attempting to LONG during a strong TRENDING_DOWN regime).
2. **Strategy Conflict**: The ensemble receives conflicting signals (e.g. Breakout says LONG but Mean Reversion says SHORT).
3. **Risk Engine Blocking**: The `RiskEngine` calculates that entering the trade would exceed the configured maximum exposure, violate a Daily Loss Limit, or that the system is currently under a forced Cooldown due to consecutive losses.
4. **Insufficient Data**: Not enough historical bars have accumulated to calculate volatility, indicators, or confirm a higher timeframe context.

### WHAT THIS SYSTEM DOES NOT DO
- **NO Guaranteed Profits**: Included baseline strategies are purely for testing the backtesting engine. They are NOT investment advice.
- **NO Live Trading**: The system is permanently firewalled against live execution.
- **NO Broker Integration**: Does not connect to or authenticate with any brokers.
- **NO Real-Money Execution**: Will not transfer money or submit live orders.
- **NO LLM Trade Decisions**: Strategies are currently deterministic math-based baselines.

## Setup Instructions

### 1. Create a virtual environment
```bash
python -m venv venv
```

### 2. Activate the virtual environment
- **Windows**: `venv\Scripts\activate`
- **Mac/Linux**: `source venv/bin/activate`

### 3. Install dependencies
```bash
pip install -r requirements.txt
# Or use pip install -e .[dev]
```

### 4. Initialize Configuration
Copy the example environment variables file and update it if necessary:
```bash
cp .env.example .env
```

### 5. Run tests
```bash
pytest
```

### 6. Sample Backtest
You can create a small script that instantiates `BacktestEngine`, loads a strategy, and passes a list of `MarketBar`s to `.run()`. Wait for future phases to see a CLI interface for backtesting!
