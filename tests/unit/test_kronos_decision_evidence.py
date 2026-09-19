"""Tests for Kronos secondary decision evidence integration."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.core.models import MarketBar, TradingSignal, MarketRegimeResult


def _make_bars(n=30, base_close=100.0):
    return [
        MarketBar(
            symbol="TEST", timestamp=datetime(2023, 1, i + 1, tzinfo=timezone.utc),
            open=base_close, high=base_close + 1, low=base_close - 1,
            close=base_close, volume=1000
        ) for i in range(n)
    ]


def _make_orchestrator(forecast_dir="UNKNOWN", risk_approved=True):
    ensemble = MagicMock()
    signal = TradingSignal(
        symbol="TEST", direction="LONG", confidence=0.7,
        strategy="BreakoutStrategy", reason="Breakout detected",
        timestamp=datetime(2023, 1, 30, tzinfo=timezone.utc)
    )
    ensemble.evaluate.return_value = signal
    ensemble.generate_signals.return_value = [signal]

    risk_engine = MagicMock()
    risk_result = MagicMock()
    risk_result.approved = risk_approved
    risk_result.rejection_reason = "Risk limit" if not risk_approved else None
    risk_engine.evaluate_trade.return_value = risk_result
    risk_engine.check_drawdown.return_value = (True, None)

    forecast_service = MagicMock()
    if forecast_dir == "UP":
        forecast_service.generate_forecast.return_value = MagicMock(
            predicted_values_json='[101.0, 102.0, 103.0]'
        )
    elif forecast_dir == "DOWN":
        forecast_service.generate_forecast.return_value = MagicMock(
            predicted_values_json='[99.0, 98.0, 97.0]'
        )
    elif forecast_dir == "EXCEPTION":
        forecast_service.generate_forecast.side_effect = RuntimeError("Kronos OOM")
    else:
        forecast_service.generate_forecast.return_value = None

    intelligence_service = MagicMock()
    intelligence_service.generate_intelligence.return_value = None

    orch = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=intelligence_service,
        forecasting_service=forecast_service,
    )
    return orch, signal


def _eval(orch, bars):
    return orch.evaluate("TEST", bars, current_equity=100000,
                         current_positions_count=0, current_exposure=0.0)


class TestKronosAgreesWithSignal:
    def test_forecast_up_signal_long_boosts_confidence(self):
        orch, signal = _make_orchestrator(forecast_dir="UP")
        decision = _eval(orch, _make_bars())
        assert decision.confidence == pytest.approx(0.75)  # 0.7 + 0.05
        assert "Kronos forecast confirms UP" in decision.rationale


class TestKronosConflictsWithSignal:
    def test_forecast_down_signal_long_reduces_confidence(self):
        orch, signal = _make_orchestrator(forecast_dir="DOWN")
        decision = _eval(orch, _make_bars())
        assert decision.confidence == pytest.approx(0.65)  # 0.7 - 0.05
        assert "Kronos forecast conflicts: DOWN" in decision.rationale


class TestKronosUnknown:
    def test_unknown_forecast_no_change(self):
        orch, signal = _make_orchestrator(forecast_dir="UNKNOWN")
        decision = _eval(orch, _make_bars())
        assert decision.confidence == pytest.approx(0.7)
        assert "Kronos" not in decision.rationale


class TestKronosUnavailable:
    def test_exception_falls_back_gracefully(self):
        orch, signal = _make_orchestrator(forecast_dir="EXCEPTION")
        decision = _eval(orch, _make_bars())
        assert decision.confidence == pytest.approx(0.7)
        assert decision.forecast_direction == "UNKNOWN"


class TestRiskEngineOverridesKronos:
    def test_risk_veto_overrides_kronos_boost(self):
        orch, signal = _make_orchestrator(forecast_dir="UP", risk_approved=False)
        decision = _eval(orch, _make_bars())
        assert decision.decision == "WAIT"
        assert decision.risk_gate_approved is False
        assert decision.paper_execution_eligible is False


class TestBoundedness:
    def test_confidence_clamped_at_one(self):
        orch, signal = _make_orchestrator(forecast_dir="UP")
        signal.confidence = 0.99
        decision = _eval(orch, _make_bars())
        assert decision.confidence <= 1.0

    def test_confidence_clamped_at_zero(self):
        orch, signal = _make_orchestrator(forecast_dir="DOWN")
        signal.confidence = 0.02
        decision = _eval(orch, _make_bars())
        assert decision.confidence >= 0.0
