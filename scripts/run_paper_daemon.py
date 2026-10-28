#!/usr/bin/env python3
"""
Production Paper-Trading Daemon Runner — Neural Trade
=====================================================
Phase 5 Live-Simulation 24/7 Daemon Script.

Runs an infinite paper-trading loop:
1. Ingests latest market bars (live via Binance Vision / CCXT or fallback to historical/mock data).
2. Evaluates active open positions against current candle for Stop Loss / Take Profit hits (1:3 RR).
3. Invokes DecisionOrchestrator for multi-strategy signals, regime detection, MTF alignment, and risk evaluation.
4. Routes approved trades to StreamingPaperBroker.
5. Captures SIGINT/SIGTERM for graceful state persistence and database checkpointing.
6. Employs rotating file logging (logs/paper_daemon.log) with exponential backoff on network disconnections.

Usage:
    python scripts/run_paper_daemon.py --symbols BTC/USDT ETH/USDT --interval 300
    python scripts/run_paper_daemon.py --offline --interval 5 --iterations 3
"""

import os
import sys
import time
import signal
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from app.config import config
from app.core.models import MarketBar, TradingSignal
from app.database.schema import init_db, SCHEMA_SQL
from app.execution.paper_repository import PaperRepository
from app.execution.streaming_paper_broker import StreamingPaperBroker, calculate_take_profit_1_to_3
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.drawdown import DrawdownService
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.breakout import BreakoutStrategy
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.forecasting.service import ForecastingService
from app.services.intelligence import IntelligenceService
from app.news.provider import FixtureNewsProvider
from app.analysis.mtf_engine import MultiTimeframeEngine
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.data.csv_provider import CsvHistoricalDataProvider
from app.data.ingestion import fetch_binance_klines, clean_and_validate_klines

logger = logging.getLogger("paper_daemon")


def setup_daemon_logging(log_file: str = "logs/paper_daemon.log", log_level: int = logging.INFO) -> logging.Logger:
    """
    Configures rotating file logging and console output for the 24/7 daemon.
    Rotates at 10MB per file with up to 5 backups to prevent disk bloat.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    d_logger = logging.getLogger("paper_daemon")
    d_logger.setLevel(log_level)

    # Avoid duplicate handlers on re-entry
    if not d_logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 1. Console Stream Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        d_logger.addHandler(console_handler)

        # 2. Rotating File Handler
        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        d_logger.addHandler(file_handler)

    return d_logger


class DaemonMarketDataProvider:
    """
    Resilient market data provider for 24/7 continuous paper execution.
    Prioritizes live public endpoints (Binance Vision / CCXT) and gracefully
    falls back to historical CSV or synthetic mock ticks for offline/testing modes.
    """

    def __init__(self, data_dir: str = "data/historical", offline: bool = False):
        self.data_dir = Path(data_dir)
        self.offline = offline
        self.csv_provider = CsvHistoricalDataProvider(str(self.data_dir))
        self._ccxt_exchange = None

        if not self.offline:
            try:
                import ccxt
                self._ccxt_exchange = ccxt.binance({
                    'enableRateLimit': True,
                    'timeout': 15000,
                    'options': {'fetchMarkets': {'types': ['spot']}},
                    'urls': {
                        'api': {
                            'public': 'https://data-api.binance.vision/api/v3',
                            'v1': 'https://data-api.binance.vision/api/v1',
                            'v3': 'https://data-api.binance.vision/api/v3'
                        }
                    }
                })
            except Exception as e:
                logger.warning("Could not initialize CCXT Binance adapter: %s. Public endpoints will be used.", e)

    def get_recent_bars(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List[MarketBar]:
        """
        Fetches the latest bars for a given symbol.
        """
        if not self.offline:
            # 1. Public Binance Vision endpoint
            try:
                raw_klines = fetch_binance_klines(symbol, timeframe, limit=limit)
                if raw_klines:
                    df = clean_and_validate_klines(raw_klines, symbol, timeframe)
                    if not df.empty:
                        bars = [
                            MarketBar(
                                symbol=symbol,
                                timestamp=r['timestamp'],
                                open=float(r['open']),
                                high=float(r['high']),
                                low=float(r['low']),
                                close=float(r['close']),
                                volume=float(r['volume'])
                            ) for _, r in df.iterrows()
                        ]
                        return bars
            except Exception as e:
                logger.warning("Binance Vision fetch failed for %s (%s): %s", symbol, timeframe, e)

            # 2. CCXT Exchange API
            if self._ccxt_exchange:
                try:
                    ohlcv = self._ccxt_exchange.fetch_ohlcv(symbol, timeframe.lower(), limit=limit)
                    if ohlcv:
                        bars = []
                        for b in ohlcv:
                            if len(b) >= 6:
                                dt = datetime.fromtimestamp(b[0] / 1000.0, tz=timezone.utc)
                                bars.append(MarketBar(
                                    symbol=symbol,
                                    timestamp=dt,
                                    open=float(b[1]),
                                    high=float(b[2]),
                                    low=float(b[3]),
                                    close=float(b[4]),
                                    volume=float(b[5])
                                ))
                        if bars:
                            return bars
                except Exception as e:
                    logger.warning("CCXT fetch failed for %s (%s): %s", symbol, timeframe, e)

        # 3. Fallback to cached historical CSV
        start_time = datetime.now(timezone.utc) - timedelta(days=365)
        csv_bars = self.csv_provider.get_historical_bars(symbol, timeframe, start_time=start_time)
        if csv_bars:
            return csv_bars[-limit:]

        return []

    def get_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> List[MarketBar]:
        """Historical bars interface used by DecisionOrchestrator and MTF engine."""
        bars = self.get_recent_bars(symbol, timeframe, limit=500)
        filtered = [b for b in bars if b.timestamp >= start_time]
        if end_time:
            filtered = [b for b in filtered if b.timestamp <= end_time]
        return filtered

    def get_latest_bar(self, symbol: str) -> Optional[MarketBar]:
        """Returns the most recent single complete bar."""
        bars = self.get_recent_bars(symbol, "1h", limit=1)
        return bars[-1] if bars else None


class PaperTradingDaemon:
    """
    24/7 Continuous Paper-Trading Daemon.
    Encapsulates lifecycle, scheduled polling, pre-trade risk gating, position exit monitoring,
    and graceful shutdown handling.
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1h",
        poll_interval: int = 300,
        portfolio_id: str = "paper_daemon_v1",
        initial_equity: float = 10000.0,
        risk_pct: float = 0.02,
        db_path: str = "data/paper_trading.db",
        historical_dir: str = "data/historical",
        log_file: str = "logs/paper_daemon.log",
        max_bars: int = 100,
        offline: bool = False,
        backoff_seconds: float = 15.0,
        max_backoff_seconds: float = 300.0,
        data_provider: Optional[Any] = None
    ):
        self.symbols = symbols or ["BTC/USDT", "ETH/USDT"]
        self.timeframe = timeframe
        self.poll_interval = poll_interval
        self.portfolio_id = portfolio_id
        self.initial_equity = initial_equity
        self.risk_pct = risk_pct
        self.db_path = db_path
        self.historical_dir = historical_dir
        self.log_file = log_file
        self.max_bars = max_bars
        self.offline = offline
        self.backoff_seconds = backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.injected_data_provider = data_provider

        self._running = False
        self.paper_repo: Optional[PaperRepository] = None
        self.risk_limits: Optional[PortfolioRiskLimits] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.broker: Optional[StreamingPaperBroker] = None
        self.market_data_provider: Optional[Any] = None
        self.orchestrator: Optional[DecisionOrchestrator] = None
        self.forecasting_service: Optional[ForecastingService] = None
        self.drawdown_service: Optional[DrawdownService] = None
        self.mtf_engine: Optional[MultiTimeframeEngine] = None
        self.ensemble: Optional[StrategyEnsemble] = None

    def setup(self) -> None:
        """
        Initializes the entire paper-trading pipeline.
        """
        # 1. Enforce paper-trading mode
        config.PAPER_TRADING = True
        config.LIVE_TRADING = False

        # 2. Database and repository initialization
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

        self.paper_repo = PaperRepository(db_path=self.db_path)
        self.paper_repo.get_or_create_portfolio(self.portfolio_id, initial_equity=self.initial_equity)

        # 3. Persistent stateful risk limits rehydration
        self.risk_limits = PortfolioRiskLimits(
            initial_equity=self.initial_equity,
            max_positions=5,
            max_exposure_pct=1.0,
            daily_loss_limit_pct=0.05,
            loss_streak_threshold=3,
            cooldown_bars=5,
            max_drawdown_halt_pct=20.0,
            survival_budget_pct=float(getattr(config, "SURVIVAL_BUDGET_PCT", 0.50))
        )
        closed_trades = self.paper_repo.get_closed_positions(self.portfolio_id, limit=100)
        self.risk_limits.rehydrate_from_paper_ledger(closed_trades)

        # 4. Authoritative pre-trade RiskEngine
        self.risk_engine = RiskEngine(limits=self.risk_limits, risk_per_trade_pct=self.risk_pct)

        # 5. Streaming paper execution broker
        self.broker = StreamingPaperBroker(
            repository=self.paper_repo,
            risk_engine=self.risk_engine,
            portfolio_id=self.portfolio_id
        )

        # 6. Market data provider
        if self.injected_data_provider is not None:
            self.market_data_provider = self.injected_data_provider
        else:
            self.market_data_provider = DaemonMarketDataProvider(
                data_dir=self.historical_dir,
                offline=self.offline
            )

        # 7. Forecasting, intelligence, drawdown, and MTF engine
        self.forecasting_service = ForecastingService(data_dir=self.historical_dir)
        self.intelligence_service = IntelligenceService(FixtureNewsProvider(), config)
        self.drawdown_service = DrawdownService()
        self.mtf_engine = MultiTimeframeEngine()

        # 8. Strategy ensemble
        self.ensemble = StrategyEnsemble([
            BreakoutStrategy(),
            TrendFollowingStrategy(),
            MeanReversionStrategy()
        ], min_score=0.0)

        # 9. Decision orchestrator
        self.orchestrator = DecisionOrchestrator(
            ensemble=self.ensemble,
            risk_engine=self.risk_engine,
            intelligence_service=self.intelligence_service,
            forecasting_service=self.forecasting_service,
            paper_repository=self.paper_repo,
            drawdown_service=self.drawdown_service,
            data_provider=self.market_data_provider,
            mtf_engine=self.mtf_engine
        )

        logger.info("Paper trading pipeline successfully initialized for portfolio '%s'.", self.portfolio_id)

    def _setup_signal_handlers(self) -> None:
        """Registers SIGINT and SIGTERM handlers for graceful shutdown."""
        def _handle_signal(signum, frame):
            sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
            logger.info("Shutdown signal %s (%s) received. Initiating graceful shutdown...", sig_name, signum)
            self.stop()

        signal.signal(signal.SIGINT, _handle_signal)
        try:
            signal.signal(signal.SIGTERM, _handle_signal)
        except (AttributeError, ValueError):
            pass  # SIGTERM may not be available on all platforms

    def stop(self) -> None:
        """Triggers graceful termination of the daemon loop."""
        self._running = False

    def _sleep_interruptible(self, seconds: float) -> None:
        """Sleeps in small slices to guarantee near-instantaneous response to shutdown signals."""
        end_time = time.time() + seconds
        while self._running and time.time() < end_time:
            time.sleep(min(0.5, max(0.05, end_time - time.time())))

    def run_iteration(self) -> Dict[str, Any]:
        """
        Performs a single evaluation cycle across all symbols:
        1. Fetches latest bar & historical series.
        2. Evaluates SL/TP exits via StreamingPaperBroker.
        3. Queries refreshed dynamic equity & portfolio exposure.
        4. Runs DecisionOrchestrator for signals, MTF alignment, and risk evaluation.
        5. Executes eligible approved orders through StreamingPaperBroker with 1:3 RR.
        """
        cycle_summary: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc),
            "exits": [],
            "decisions": {},
            "executions": []
        }

        for symbol in self.symbols:
            logger.info("[%s] Polling market bars...", symbol)
            bars = self.market_data_provider.get_recent_bars(symbol, self.timeframe, limit=self.max_bars)
            if not bars:
                logger.warning("[%s] No market bars retrieved. Skipping cycle for symbol.", symbol)
                continue

            latest_bar = bars[-1]
            logger.info(
                "[%s] Latest Bar: %s | O:%.2f H:%.2f L:%.2f C:%.2f V:%.2f",
                symbol, latest_bar.timestamp.isoformat(),
                latest_bar.open, latest_bar.high, latest_bar.low, latest_bar.close, latest_bar.volume
            )

            # Step 1: Monitor SL/TP for open positions (1:3 RR runtime check)
            exits = self.broker.monitor_positions(latest_bar)
            if exits:
                for exit_event in exits:
                    logger.info(
                        "[%s] Exit Triggered: Pos #%s | Reason: %s | Exit Price: %.2f | Success: %s",
                        symbol, exit_event.get("position_id"), exit_event.get("reason"),
                        exit_event.get("price", 0.0), exit_event.get("success")
                    )
                    cycle_summary["exits"].append(exit_event)

            # Step 2: Query real-time dynamic portfolio state
            state = self.broker.get_realtime_portfolio()
            current_positions_count = len(state.open_positions)
            current_exposure = sum(p['quantity'] * p['entry_price'] for p in state.open_positions)

            portfolio_row = self.paper_repo.get_or_create_portfolio(self.portfolio_id)
            current_equity = float(portfolio_row['current_equity'])

            # Phase 67 — Death Mode (Survival Budget) Halt Check
            if self.risk_limits.is_survival_budget_breached(current_equity):
                self.risk_engine.death_mode_active = True
                self.risk_engine.death_mode_reason = "Survival budget breached."

            if getattr(self.risk_engine, "death_mode_active", False):
                logger.critical("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                logger.critical("SYSTEM DEAD: SURVIVAL BUDGET BREACHED")
                logger.critical(
                    "Dynamic equity $%.2f breached survival threshold $%.2f. Permanently halting trading daemon.",
                    current_equity, getattr(self.risk_limits, "survival_budget_threshold", 0.0)
                )
                logger.critical("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                self.stop()
                break

            existing_pos = next((p for p in state.open_positions if p['symbol'] == symbol), None)

            # Step 3: Evaluate orchestrator for new entry signal
            decision = self.orchestrator.evaluate(
                symbol=symbol,
                bars=bars,
                current_equity=current_equity,
                current_positions_count=current_positions_count,
                current_exposure=current_exposure,
                portfolio_id=self.portfolio_id
            )
            cycle_summary["decisions"][symbol] = decision.decision

            logger.info(
                "[%s] Decision: %s (Conf: %.2f) | Regime: %s | Risk Gate: %s | Reason: %s",
                symbol, decision.decision, decision.confidence, decision.regime,
                "Approved" if decision.risk_gate_approved else "Vetoed", decision.rationale
            )

            # Step 4: Route approved signals to broker
            if decision.paper_execution_eligible and decision.decision in ("LONG", "SHORT", "BUY", "SELL"):
                # If already holding an active position in the SAME direction, skip opening duplicate
                if existing_pos and existing_pos['direction'] == decision.decision:
                    logger.info("[%s] Position already open in %s direction. Skipping duplicate entry.", symbol, decision.decision)
                    continue

                # Enforce Stop Loss and 1:3 RR Take Profit
                sl = decision.stop_loss
                if sl is None:
                    sl = decision.evaluated_price * 0.95 if decision.decision in ("LONG", "BUY") else decision.evaluated_price * 1.05

                tp = decision.take_profit
                if tp is None:
                    tp = calculate_take_profit_1_to_3(decision.evaluated_price, sl, decision.decision)

                actual_strategy = "DaemonEnsemble"
                if decision.strategy_signals:
                    actual_strategy = ",".join(sorted(set(s.get("strategy", "Unknown") for s in decision.strategy_signals)))

                signal_obj = TradingSignal(
                    symbol=symbol,
                    timestamp=latest_bar.timestamp,
                    direction=decision.decision,
                    strategy=actual_strategy,
                    confidence=decision.confidence,
                    entry_price=decision.evaluated_price,
                    stop_loss=sl,
                    take_profit=tp,
                    reason=decision.rationale
                )

                # Pre-trade risk validation
                risk_eval = self.risk_engine.evaluate_trade(
                    signal=signal_obj,
                    current_equity=current_equity,
                    current_positions_count=current_positions_count,
                    current_exposure=current_exposure
                )

                if risk_eval.approved:
                    executed = self.broker.execute_decision(
                        decision=decision,
                        position_size=risk_eval.position_size,
                        stop_loss=sl,
                        take_profit=tp
                    )
                    if executed:
                        logger.info(
                            "[%s] ORDER EXECUTED: %s %.4f @ %.2f | SL: %.2f | TP: %.2f (1:3 RR)",
                            symbol, decision.decision, risk_eval.position_size, decision.evaluated_price, sl, tp
                        )
                        cycle_summary["executions"].append({
                            "symbol": symbol,
                            "direction": decision.decision,
                            "size": risk_eval.position_size,
                            "price": decision.evaluated_price,
                            "stop_loss": sl,
                            "take_profit": tp
                        })
                    else:
                        logger.warning("[%s] Order execution rejected by broker internal verification.", symbol)
                else:
                    logger.warning("[%s] Order vetoed by RiskEngine: %s", symbol, risk_eval.rejection_reason)
            else:
                if decision.decision not in ("WAIT", "NO TRADE"):
                    logger.info("[%s] Decision %s not eligible for paper execution: %s", symbol, decision.decision, decision.risk_gate_reason)

        return cycle_summary

    def _shutdown(self) -> None:
        """
        Safely saves database state, synchronizes dynamic equity, and logs final portfolio metrics.
        """
        logger.info("================================================================================")
        logger.info("Graceful shutdown in progress: syncing portfolio state...")
        try:
            if self.paper_repo and self.broker:
                dynamic_equity = self.paper_repo.sync_dynamic_equity(
                    self.portfolio_id,
                    current_prices=self.broker.latest_prices
                )
                state = self.broker.get_realtime_portfolio()
                port = self.paper_repo.get_or_create_portfolio(self.portfolio_id)
                cash = port['current_cash'] if 'current_cash' in port.keys() else port['current_equity']

                logger.info("-------------------- PORTFOLIO FINAL STATE --------------------")
                logger.info("Portfolio ID:       %s", self.portfolio_id)
                logger.info("Dynamic Equity:     $%.2f", dynamic_equity)
                logger.info("Realized Cash:      $%.2f", float(cash))
                logger.info("Open Positions:     %d", len(state.open_positions))
                for p in state.open_positions:
                    logger.info(
                        "  -> %s %s %.4f @ $%.2f (SL: %s, TP: %s)",
                        p['symbol'], p['direction'], p['quantity'], p['entry_price'], p['stop_loss'], p['take_profit']
                    )
                logger.info("----------------------------------------------------------------")
        except Exception as e:
            logger.error("Error during final state sync: %s", e)

        logger.info("Database transactions committed. Paper trading daemon safely terminated.")
        logger.info("================================================================================")

    def start(self, max_iterations: Optional[int] = None) -> None:
        """
        Main 24/7 daemon loop with network error resilience, exponential backoff, and graceful exit.
        """
        self.setup()
        self._running = True
        self._setup_signal_handlers()

        logger.info("================================================================================")
        logger.info("Starting Paper Trading Daemon (Phase 5 Continuous Simulation)")
        logger.info("Portfolio ID: %s | Symbols: %s | Timeframe: %s", self.portfolio_id, self.symbols, self.timeframe)
        logger.info("Poll Interval: %ds | Backoff Baseline: %.1fs", self.poll_interval, self.backoff_seconds)
        logger.info("================================================================================")

        iteration = 0
        consecutive_errors = 0
        current_backoff = self.backoff_seconds

        try:
            while self._running:
                if max_iterations is not None and iteration >= max_iterations:
                    logger.info("Reached maximum specified iterations (%d). Exiting daemon loop.", max_iterations)
                    break

                iteration += 1
                logger.info("--- Iteration #%d starting at %s ---", iteration, datetime.now(timezone.utc).isoformat())

                try:
                    self.run_iteration()

                    # Phase 67 — Death Mode (Survival Budget) Loop Check
                    if getattr(self.risk_engine, "death_mode_active", False):
                        logger.critical("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        logger.critical("SYSTEM DEAD: SURVIVAL BUDGET BREACHED")
                        logger.critical("Halting paper daemon process immediately.")
                        logger.critical("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        self.stop()
                        break

                    # Reset error counters on successful cycle
                    consecutive_errors = 0
                    current_backoff = self.backoff_seconds

                    if self._running:
                        logger.info("Cycle completed. Sleeping for %ds...", self.poll_interval)
                        self._sleep_interruptible(self.poll_interval)

                except (ConnectionError, TimeoutError, urllib.error.URLError, OSError) as net_err:
                    consecutive_errors += 1
                    current_backoff = min(self.max_backoff_seconds, self.backoff_seconds * (1.5 ** (consecutive_errors - 1)))
                    logger.warning(
                        "Network/Connection error during iteration #%d: %s. Consecutive errors: %d. Backing off for %.1fs.",
                        iteration, net_err, consecutive_errors, current_backoff
                    )
                    self._sleep_interruptible(current_backoff)

                except Exception as exc:
                    consecutive_errors += 1
                    current_backoff = min(self.max_backoff_seconds, self.backoff_seconds * (1.5 ** (consecutive_errors - 1)))
                    logger.exception(
                        "Unexpected error during daemon iteration #%d: %s. Consecutive errors: %d. Backing off for %.1fs.",
                        iteration, exc, consecutive_errors, current_backoff
                    )
                    self._sleep_interruptible(current_backoff)

        finally:
            self._shutdown()


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for the paper daemon."""
    parser = argparse.ArgumentParser(description="24/7 Paper Trading Daemon Runner — Neural Trade")
    parser.add_argument("--symbols", nargs="+", default=["BTC/USDT", "ETH/USDT"], help="Symbols to trade (e.g. BTC/USDT ETH/USDT)")
    parser.add_argument("--timeframe", default="1h", help="Trading timeframe (default: 1h)")
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds (default: 300)")
    parser.add_argument("--portfolio-id", default="paper_daemon_v1", help="Paper portfolio ID (default: paper_daemon_v1)")
    parser.add_argument("--initial-equity", type=float, default=10000.0, help="Initial portfolio equity (default: 10000.0)")
    parser.add_argument("--risk-pct", type=float, default=0.02, help="Risk percentage per trade (default: 0.02)")
    parser.add_argument("--db-path", default="data/paper_trading.db", help="SQLite database path")
    parser.add_argument("--historical-dir", default="data/historical", help="Historical data directory")
    parser.add_argument("--log-file", default="logs/paper_daemon.log", help="Rotating log file destination")
    parser.add_argument("--max-bars", type=int, default=100, help="Lookback window size (default: 100)")
    parser.add_argument("--offline", action="store_true", help="Run offline using cached historical CSV files")
    parser.add_argument("--iterations", type=int, default=None, help="Max iterations to run before stopping (for testing)")
    parser.add_argument("--backoff", type=float, default=15.0, help="Initial error backoff in seconds (default: 15.0)")
    return parser.parse_args()


def main():
    args = parse_arguments()
    setup_daemon_logging(log_file=args.log_file)
    daemon = PaperTradingDaemon(
        symbols=args.symbols,
        timeframe=args.timeframe,
        poll_interval=args.interval,
        portfolio_id=args.portfolio_id,
        initial_equity=args.initial_equity,
        risk_pct=args.risk_pct,
        db_path=args.db_path,
        historical_dir=args.historical_dir,
        log_file=args.log_file,
        max_bars=args.max_bars,
        offline=args.offline,
        backoff_seconds=args.backoff
    )
    daemon.start(max_iterations=args.iterations)


if __name__ == "__main__":
    main()
