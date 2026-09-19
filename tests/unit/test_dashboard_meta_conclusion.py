import pytest
from unittest.mock import patch, MagicMock
from app.dashboard.components.trader_decision import render_trader_decision_tab
from app.decision.models import TraderDecision, ScenarioAnalysis
from app.execution.paper_repository import PaperRepository

@patch("app.dashboard.components.trader_decision.st")
@patch("app.dashboard.components.trader_decision.DecisionOrchestrator")
@patch("app.dashboard.components.trader_decision.PaperRepository")
def test_dashboard_renders_meta_conclusion(mock_repo_class, mock_orchestrator_class, mock_st):
    mock_repo_class.return_value = MagicMock()
    mock_st.columns.side_effect = lambda x: [MagicMock() for _ in range(x)] if isinstance(x, int) else [MagicMock() for _ in range(len(x))]
    mock_st.button.return_value = True
    
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    
    import datetime
    
    # Mock evaluate to return a TraderDecision with meta_conclusion
    mock_orchestrator.evaluate.return_value = TraderDecision(
        symbol="BTC/USD",
        timestamp=datetime.datetime.utcnow(),
        data_freshness="FRESH",
        regime="TRENDING_UP",
        trend_context="TRENDING_UP",
        volatility_context="NORMAL",
        multi_timeframe_alignment="ALIGNED_BULLISH",
        portfolio_correlation="LOW_CORRELATION",
        strategy_signals=[{"strategy": "BreakoutStrategy", "direction": "LONG"}],
        forecast_direction="UP",
        forecast_uncertainty=0.5,
        world_context="POSITIVE",
        scenario_analysis=ScenarioAnalysis(bullish_scenario="B", bearish_scenario="B", neutral_scenario="N"),
        main_risks=["Risk"],
        invalidation_conditions=["Inv"],
        rationale="Rational",
        confidence=0.8,
        decision="LONG",
        evaluated_price=100.0,
        risk_gate_approved=True,
        risk_gate_reason=None,
        paper_execution_eligible=True,
        strategy_weighting_audit={
            "BreakoutStrategy": {
                "weight_multiplier": 1.25,
                "reason": "ESTABLISHED_WITHIN_TESTED_SCOPE",
                "evidence_age_days": 5.0,
                "meta_conclusion": {
                    "evidence_state": "ESTABLISHED_WITHIN_TESTED_SCOPE",
                    "statement": "Strong support",
                    "independent_evidence_count": 5,
                    "total_evidence_count": 10
                }
            }
        }
    )
    
    render_trader_decision_tab()
    
    mock_st.markdown.assert_any_call("**Meta-Analysis Status:** :green[**ESTABLISHED_WITHIN_TESTED_SCOPE**]")
    mock_st.markdown.assert_any_call("**Synthesis:** Strong support")
    mock_st.caption.assert_any_call("Evidence: 5 independent datasets / 10 total samples")

@patch("app.dashboard.components.trader_decision.st")
@patch("app.dashboard.components.trader_decision.DecisionOrchestrator")
@patch("app.dashboard.components.trader_decision.PaperRepository")
def test_dashboard_renders_missing_meta_conclusion(mock_repo_class, mock_orchestrator_class, mock_st):
    mock_repo_class.return_value = MagicMock()
    mock_st.columns.side_effect = lambda x: [MagicMock() for _ in range(x)] if isinstance(x, int) else [MagicMock() for _ in range(len(x))]
    mock_st.button.return_value = True
    
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    
    import datetime
    
    mock_orchestrator.evaluate.return_value = TraderDecision(
        symbol="BTC/USD",
        timestamp=datetime.datetime.utcnow(),
        data_freshness="FRESH",
        regime="TRENDING_UP",
        trend_context="TRENDING_UP",
        volatility_context="NORMAL",
        multi_timeframe_alignment="ALIGNED_BULLISH",
        portfolio_correlation="LOW_CORRELATION",
        strategy_signals=[{"strategy": "BreakoutStrategy", "direction": "LONG"}],
        forecast_direction="UP",
        forecast_uncertainty=0.5,
        world_context="POSITIVE",
        scenario_analysis=ScenarioAnalysis(bullish_scenario="B", bearish_scenario="B", neutral_scenario="N"),
        main_risks=["Risk"],
        invalidation_conditions=["Inv"],
        rationale="Rational",
        confidence=0.8,
        decision="LONG",
        evaluated_price=100.0,
        risk_gate_approved=True,
        risk_gate_reason=None,
        paper_execution_eligible=True,
        strategy_weighting_audit={
            "BreakoutStrategy": {
                "weight_multiplier": 1.0,
                "reason": "META_ANALYSIS_FAILED",
                "evidence_age_days": None,
                "meta_conclusion": None
            }
        }
    )
    
    render_trader_decision_tab()
    
    mock_st.write.assert_any_call("No meta-analysis conclusion available.")
    mock_st.write.assert_any_call("**Evidence Age:** N/A")
