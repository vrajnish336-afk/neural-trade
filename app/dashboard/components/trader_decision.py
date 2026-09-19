import streamlit as st
import datetime
import json
from app.decision.models import TraderDecision, ScenarioAnalysis
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.breakout import BreakoutStrategy
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.services.intelligence import IntelligenceService
from app.news.provider import FixtureNewsProvider
from app.forecasting.service import ForecastingService
from app.config import config
from app.data.csv_provider import CsvHistoricalDataProvider

from app.execution.paper_repository import PaperRepository
from app.risk.drawdown import DrawdownService, DrawdownStatus
import pandas as pd

def render_trader_decision_tab():
    st.markdown("## Unified Trader Decision Loop")
    st.warning("⚠️ PAPER / RESEARCH ONLY. LIVE TRADING PERMANENTLY DISABLED. No broker integration exists.")

    # 1. Paper Portfolio State (Read Only)
    st.markdown("### Persistent Paper Portfolio (default_paper)")
    try:
        repo = PaperRepository()
        portfolio = repo.get_or_create_portfolio("default_paper")
        positions = repo.get_open_positions("default_paper")
        orders = repo.get_recent_orders("default_paper", limit=5)
        
        col_eq, col_cash, col_pos = st.columns(3)
        col_eq.metric("Current Equity", f"${portfolio['current_equity']:.2f}")
        col_cash.metric("Current Cash", f"${portfolio['current_cash']:.2f}")
        col_pos.metric("Open Positions", len(positions))
        
        st.markdown("#### Paper Portfolio Performance")
        
        # Pull snapshots for equity curve
        snapshots = repo.get_equity_snapshots("default_paper")
        if snapshots:
            st.markdown("**Equity Curve (USD)**")
            eq_data = pd.DataFrame([{
                'Time': pd.to_datetime(s['timestamp']),
                'Equity': s['current_equity']
            } for s in snapshots])
            eq_data.set_index('Time', inplace=True)
            st.line_chart(eq_data['Equity'])
        else:
            st.write("Equity Curve Unavailable: Not enough history.")
            
        # Pull closed positions for daily PnL
        closed_positions = repo.get_closed_positions("default_paper", limit=1000)
        
        cumulative_pnl = 0.0
        
        if closed_positions:
            st.markdown("**Daily Realized Gross PnL (USD)**")
            pnl_data = pd.DataFrame([{
                'Date': pd.to_datetime(cp['exit_time']).date(),
                'Gross PnL': cp['realized_pnl']
            } for cp in closed_positions])
            
            daily_pnl = pnl_data.groupby('Date')['Gross PnL'].sum().reset_index()
            daily_pnl.set_index('Date', inplace=True)
            st.bar_chart(daily_pnl['Gross PnL'])
            
            cumulative_pnl = sum(cp['realized_pnl'] for cp in closed_positions)
        else:
            st.write("Daily Realized PnL Unavailable: No closed positions.")
            
        c1, c2 = st.columns(2)
        c1.metric("Cumulative Realized Gross PnL", f"${cumulative_pnl:.2f}")
        c2.metric("Closed Trades Count", len(closed_positions))
        
        # ---- Portfolio Drawdown (Phase 58) ----
        st.markdown("**Portfolio Drawdown (Realised Equity)**")
        _render_drawdown_panel(snapshots, limits_halt_pct=20.0)
        
        st.markdown("---")
        st.markdown("#### Open Positions")
        if positions:
            for p in positions:
                st.markdown(f"**{p['symbol']}** | {p['direction']} | Qty: {p['quantity']} | Entry: ${p['entry_price']:.2f}")
                
                exit_price = None
                exit_ts = None
                try:
                    provider = CsvHistoricalDataProvider(data_dir="data/sample")
                    # Use a fixed date for evaluation sync or just timezone now, provider uses what's available
                    bars = provider.get_historical_bars(p['symbol'], "1D", datetime.datetime.now(datetime.timezone.utc))
                    if bars:
                        exit_price = bars[-1].close
                        exit_ts = bars[-1].timestamp
                except Exception:
                    pass
                
                if exit_price and exit_ts:
                    if st.button(f"Initiate Exit: {p['symbol']} @ ${exit_price:.2f}", key=f"exit_btn_{p['position_id']}"):
                        st.session_state[f"confirm_exit_{p['position_id']}"] = True
                        
                    if st.session_state.get(f"confirm_exit_{p['position_id']}", False):
                        st.warning(f"Confirm closing {p['symbol']} position {p['position_id']} at ${exit_price:.2f}?")
                        c_conf, c_canc = st.columns(2)
                        if c_conf.button("✅ Confirm Exit", key=f"confirm_{p['position_id']}"):
                            from app.execution.streaming_paper_broker import StreamingPaperBroker
                            from app.backtesting.models import CostConfig
                            
                            # Instantiate broker just for the exit action (RiskEngine is mocked minimally as it's not strictly evaluating a new signal here)
                            limits = PortfolioRiskLimits(initial_equity=10000.0)
                            risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
                            broker = StreamingPaperBroker(repo, risk_engine, CostConfig(), "default_paper")
                            
                            success = broker.execute_exit(
                                position_id=p['position_id'],
                                exit_price=exit_price,
                                timestamp=exit_ts
                            )
                            if success:
                                st.success(f"Exit persisted for {p['symbol']}.")
                                st.session_state[f"confirm_exit_{p['position_id']}"] = False
                                st.rerun()
                            else:
                                st.error("Exit failed or rejected by repository.")
                                
                        if c_canc.button("❌ Cancel", key=f"cancel_{p['position_id']}"):
                            st.session_state[f"confirm_exit_{p['position_id']}"] = False
                            st.rerun()
                else:
                    st.button(f"Exit {p['symbol']} (Disabled)", key=f"exit_btn_{p['position_id']}", disabled=True)
                    st.caption("ℹ️ Exit disabled: Valid current/evaluated price is unavailable from data provider.")
                st.markdown("---")
        else:
            st.write("No open positions.")
            
        st.markdown("#### Recently Closed Paper Positions")
        closed_positions = repo.get_closed_positions("default_paper", limit=1000)
        
        if closed_positions:
            # Group by strategy
            st.markdown("##### Strategy-Level Completed Trade Analytics")
            strat_data = []
            strat_groups = {}
            for cp in closed_positions:
                strat = cp['strategy'] if 'strategy' in cp.keys() else 'Unavailable'
                strat = strat or 'Unavailable'
                if strat not in strat_groups:
                    strat_groups[strat] = {'trades': 0, 'wins': 0, 'realized_pnl': 0.0}
                strat_groups[strat]['trades'] += 1
                if cp['realized_pnl'] > 0:
                    strat_groups[strat]['wins'] += 1
                strat_groups[strat]['realized_pnl'] += cp['realized_pnl']
                
            for strat, metrics in strat_groups.items():
                win_rate = (metrics['wins'] / metrics['trades']) * 100.0 if metrics['trades'] > 0 else 0.0
                strat_data.append({
                    "Strategy Identity": strat,
                    "Completed Trades": metrics['trades'],
                    "Win Rate": f"{win_rate:.1f}%",
                    "Realized Gross PnL": f"${metrics['realized_pnl']:.2f}"
                })
            st.dataframe(pd.DataFrame(strat_data), use_container_width=True)
            
            st.markdown("##### Recent Individual Completed Trades")
            for cp in closed_positions[:10]:
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                c1.markdown(f"**{cp['symbol']}** | {cp['direction']} | Qty: {cp['quantity']}")
                c2.write(f"In: ${cp['entry_price']:.2f}")
                c3.write(f"Out: ${cp['exit_price']:.2f}")
                
                # Format PnL distinctly
                pnl = cp['realized_pnl']
                pnl_color = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
                c4.markdown(f"{pnl_color} **${pnl:.2f}**")
                
                strat_val = cp['strategy'] if 'strategy' in cp.keys() else 'Unavailable'
                strat_val = strat_val or 'Unavailable'
                st.caption(f"Strategy: {strat_val} | Entered: {cp['entry_time']} | Exited: {cp['exit_time']} | Reason: {cp['exit_reason']}")
                st.markdown("---")
        else:
            st.write("No completed trades.")
            
        st.markdown("#### Recent Paper Orders")
        if orders:
            ord_data = []
            for o in orders:
                strat_val = o['strategy'] if 'strategy' in o.keys() else 'Unavailable'
                strat_val = strat_val or 'Unavailable'
                ord_data.append({
                    "Time": o['timestamp'],
                    "Symbol": o['symbol'],
                    "Side": o['direction'],
                    "Qty": o['quantity'],
                    "Price": f"${o['price']:.2f}",
                    "Status": o['status'],
                    "Strategy": strat_val,
                    "Slippage": f"${o['slippage']:.4f}",
                    "Comm.": f"${o['commission']:.4f}"
                })
            st.dataframe(pd.DataFrame(ord_data), use_container_width=True)
        else:
            st.write("No recent orders.")
            
    except Exception as e:
        st.error(f"Failed to load paper portfolio state: {e}")

    st.markdown("---")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.markdown("### Inputs")
        symbol = st.selectbox("Symbol", ["synthetic_test_data", "BTC/USD", "ETH/USD"], key="td_symbol")
        run_decision = st.button("Evaluate Decision Loop", type="primary")

    if run_decision:
        with st.spinner("Aggregating Market Data, Intelligence, and Forecasts..."):
            try:
                # Setup
                provider = CsvHistoricalDataProvider(data_dir="data/sample")
                bars = provider.get_historical_bars(symbol, "1D", datetime.datetime(2023,1,1, tzinfo=datetime.timezone.utc))
                
                strategy = BreakoutStrategy()
                ensemble = StrategyEnsemble([strategy])
                
                limits = PortfolioRiskLimits(initial_equity=10000.0)
                risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
                
                news_provider = FixtureNewsProvider()
                intelligence_service = IntelligenceService(news_provider, config)
                
                forecasting_service = ForecastingService()
                
                from app.decision.weighting import StrategyWeightingService
                weighting_service = StrategyWeightingService()
                
                orchestrator = DecisionOrchestrator(
                    ensemble=ensemble,
                    risk_engine=risk_engine,
                    intelligence_service=intelligence_service,
                    forecasting_service=forecasting_service,
                    paper_repository=st.session_state.paper_db,
                    drawdown_service=DrawdownService(),
                    weighting_service=StrategyWeightingService(st.session_state.evolution_db),
                    data_provider=provider
                )
                
                # We limit bars to 100 for evaluation speed
                eval_bars = bars[:100] if bars else []
                
                decision: TraderDecision = orchestrator.evaluate(
                    symbol=symbol,
                    bars=eval_bars,
                    current_equity=10000.0,
                    current_positions_count=0,
                    current_exposure=0.0
                )
                
                # Render Results
                st.markdown("### Decision Output")
                
                # Top Row
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Selected Symbol", decision.symbol)
                c2.metric("Timestamp", decision.timestamp.strftime("%Y-%m-%d %H:%M") if decision.timestamp else "N/A")
                c3.metric("Data Freshness", decision.data_freshness)
                c4.metric("Market Regime", decision.regime)
                
                # Second Row
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Final Decision", decision.decision, 
                          delta="APPROVED" if decision.risk_gate_approved else "REJECTED", 
                          delta_color="normal" if decision.risk_gate_approved else "inverse")
                c2.metric("Confidence", f"{decision.confidence*100:.1f}%")
                c3.metric("MTF Alignment", decision.multi_timeframe_alignment)
                c4.metric("Port. Correlation", decision.portfolio_correlation)
                
                # Third Row
                c1, c2, c3 = st.columns(3)
                c1.metric("Forecast Direction", decision.forecast_direction)
                c2.metric("World Context", decision.world_context)
                
                # Details
                st.markdown("#### Scenario Analysis")
                s1, s2, s3 = st.columns(3)
                with s1:
                    st.info(f"**Bullish Scenario:**\n\n{decision.scenario_analysis.bullish_scenario}")
                with s2:
                    st.error(f"**Bearish Scenario:**\n\n{decision.scenario_analysis.bearish_scenario}")
                with s3:
                    st.warning(f"**Neutral Scenario:**\n\n{decision.scenario_analysis.neutral_scenario}")
                    
                st.markdown("#### Decision Rationale")
                st.write(decision.rationale)
                
                st.markdown("#### Risk Gate")
                if decision.risk_gate_approved:
                    st.success("Risk Gate: APPROVED")
                else:
                    st.error(f"Risk Gate: REJECTED - {decision.risk_gate_reason}")
                
                if not decision.risk_gate_approved:
                    st.warning("A rejected decision must never reach paper execution.")
                else:
                    st.info("Paper action status: Eligible for paper execution.")
                    
                st.markdown("#### Signals & Bounded Weighting Audit")
                
                if decision.strategy_weighting_audit:
                    for strat, audit in decision.strategy_weighting_audit.items():
                        with st.expander(f"Strategy: {strat} | Multiplier: {audit.get('weight_multiplier', 1.0):.2f}x", expanded=True):
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                st.write(f"**Fallback / Adjust Reason:** {audit.get('reason', 'N/A')}")
                                age = audit.get('evidence_age_days')
                                st.write(f"**Evidence Age:** {f'{age:.1f} days' if age is not None else 'N/A'}")
                                
                            with c2:
                                mc = audit.get("meta_conclusion")
                                if mc:
                                    status = mc.get('evidence_state', 'UNKNOWN')
                                    color = "blue"
                                    if status == "ESTABLISHED_WITHIN_TESTED_SCOPE": color = "green"
                                    elif status in ["CONFLICTED", "PROMISING_BUT_FRAGILE"]: color = "orange"
                                    elif status == "FALSIFIED_WITHIN_TESTED_SCOPE": color = "red"
                                    elif status == "INSUFFICIENT_EVIDENCE": color = "grey"
                                    
                                    st.markdown(f"**Meta-Analysis Status:** :{color}[**{status}**]")
                                    st.markdown(f"**Synthesis:** {mc.get('statement', 'N/A')}")
                                    st.caption(f"Evidence: {mc.get('independent_evidence_count', 0)} independent datasets / {mc.get('total_evidence_count', 0)} total samples")
                                else:
                                    st.write("No meta-analysis conclusion available.")
                else:
                    st.write("No strategies evaluated or weighting audit missing.")

                st.markdown("#### Risk & Invalidation")
                st.json({
                    "main_risks": decision.main_risks,
                    "invalidation_conditions": decision.invalidation_conditions
                })
                
            except Exception as e:
                st.error(f"Error evaluating decision loop: {str(e)}")
                import traceback
                st.code(traceback.format_exc())


# ---------------------------------------------------------------------------
# Portfolio Drawdown Panel — Phase 58
# Read-only display helper.  No DB writes.  No execution.
# ---------------------------------------------------------------------------
def _render_drawdown_panel(snapshots, *, limits_halt_pct: float = 20.0) -> None:
    """
    Renders drawdown metrics inside the existing Paper Portfolio Performance area.

    Args:
        snapshots: list of sqlite3.Row from PaperRepository.get_equity_snapshots()
        limits_halt_pct: configured halt threshold (percentage, e.g. 20.0)
    """
    svc = DrawdownService()
    dd = svc.calculate(snapshots, has_partial_history=(len(snapshots) < 3))

    if dd.status == DrawdownStatus.INSUFFICIENT_DATA:
        st.info(
            f"⚠️ Drawdown Unavailable — {dd.reason} "
            "Equity snapshots are recorded on each entry/exit. "
            "Execute at least one round-trip to generate history."
        )
        return

    if dd.status == DrawdownStatus.INVALID_DATA:
        st.error(f"❌ Drawdown INVALID DATA — {dd.reason}")
        return

    # Status == OK — display metrics
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Current Drawdown", f"{dd.current_drawdown_pct:.2f}%")
    col_b.metric("Max Observed Drawdown", f"{dd.max_drawdown_pct:.2f}%")
    col_c.metric("Running Peak Equity", f"${dd.running_peak_equity:.2f}")
    col_d.metric("Current Equity (snapshots)", f"${dd.current_equity:.2f}")

    # Threshold status
    if dd.current_drawdown_pct >= limits_halt_pct:
        st.error(
            f"🛑 DRAWDOWN HALT ACTIVE — current {dd.current_drawdown_pct:.2f}% "
            f">= threshold {limits_halt_pct:.2f}%. New positions blocked by RiskEngine."
        )
    else:
        st.success(
            f"✅ Drawdown within limits — {dd.current_drawdown_pct:.2f}% "
            f"< threshold {limits_halt_pct:.2f}%."
        )

    # Observation window
    st.caption(
        f"Observation window: {dd.observation_start} → {dd.observation_end} "
        f"| Snapshots: {dd.snapshot_count}"
        + (" | ⚠️ Partial history — data may not extend to portfolio creation." if dd.has_partial_history else "")
    )

    st.caption(
        "📌 Equity basis: realised cash only (commissions deducted at entry; "
        "net PnL applied at exit). Unrealised open-position value NOT included."
    )
    st.caption(
        f"Threshold: {limits_halt_pct:.1f}% drawdown halt (configurable via PortfolioRiskLimits.max_drawdown_halt_pct). "
        "PAPER TRADING ONLY — LIVE TRADING DISABLED."
    )
