import pytest
from unittest.mock import patch, MagicMock
from app.dashboard.components.death_mode_banner import render_death_mode_banner
from app.dashboard.components.system_config import render_system_config_tab
from app.dashboard.components.trader_decision import render_trader_decision_tab
from app.execution.paper_repository import PaperRepository
import sqlite3
import tempfile
import os
from app.database.schema import SCHEMA_SQL

@patch("streamlit.markdown")
def test_death_mode_banner_active_when_equity_breached(mock_markdown):
    """When equity <= 50% of initial equity, renders blinking red neon banner."""
    rendered = render_death_mode_banner(
        current_equity=4500.0,
        initial_equity=10000.0,
        survival_budget_pct=0.50
    )
    assert rendered is True
    assert mock_markdown.called
    html_arg = mock_markdown.call_args[0][0]
    assert "neon-death-banner" in html_arg
    assert "DEATH MODE ACTIVE" in html_arg
    assert "SURVIVAL BUDGET BREACHED" in html_arg
    assert "neon-death-blink" in html_arg


@patch("streamlit.markdown")
def test_death_mode_banner_active_flag_override(mock_markdown):
    """When is_active is True, renders blinking red neon banner regardless of equity."""
    rendered = render_death_mode_banner(
        current_equity=8000.0,
        initial_equity=10000.0,
        survival_budget_pct=0.50,
        is_active=True
    )
    assert rendered is True
    assert mock_markdown.called
    html_arg = mock_markdown.call_args[0][0]
    assert "neon-death-banner" in html_arg
    assert "DEATH MODE ACTIVE" in html_arg


@patch("streamlit.markdown")
def test_death_mode_banner_near_threshold_warning(mock_markdown):
    """When equity is within 15% buffer above the 50% floor, renders near-threshold warning banner."""
    # Floor = 5000. Near threshold = 5000 * 1.15 = 5750
    rendered = render_death_mode_banner(
        current_equity=5400.0,
        initial_equity=10000.0,
        survival_budget_pct=0.50,
        buffer_pct=0.15
    )
    assert rendered is True
    assert mock_markdown.called
    html_arg = mock_markdown.call_args[0][0]
    assert "neon-warn-banner" in html_arg
    assert "NEAR DEATH MODE SURVIVAL THRESHOLD" in html_arg


@patch("streamlit.markdown")
def test_death_mode_banner_healthy_equity(mock_markdown):
    """When equity is healthy (e.g. $10,000), no death or warning banner is rendered."""
    rendered = render_death_mode_banner(
        current_equity=10000.0,
        initial_equity=10000.0,
        survival_budget_pct=0.50
    )
    assert rendered is False
    assert mock_markdown.called is False


@patch("app.dashboard.components.death_mode_banner.st.markdown")
@patch("streamlit.warning")
@patch("streamlit.table")
@patch("app.dashboard.components.system_config.PaperRepository")
@patch("app.learning.paper_evolution_repository.PaperEvolutionRepository")
def test_system_config_tab_displays_death_mode_banner(
    mock_evo, mock_repo_class, mock_table, mock_warning, mock_markdown
):
    """Verifies that render_system_config_tab surfaces the neon banner when equity is breached."""
    mock_repo = MagicMock()
    mock_repo.get_or_create_portfolio.return_value = {
        'initial_equity': 10000.0,
        'current_equity': 4200.0
    }
    mock_repo.get_closed_positions.return_value = []
    mock_repo_class.return_value = mock_repo

    mock_evo_inst = mock_evo.return_value
    mock_evo_inst.get_lessons.return_value = []
    mock_evo_inst.get_proposals.return_value = []

    render_system_config_tab()

    # Check that markdown received the death banner HTML
    markdown_calls = [call[0][0] for call in mock_markdown.call_args_list if len(call[0]) > 0 and isinstance(call[0][0], str)]
    assert any("neon-death-banner" in content for content in markdown_calls)


@patch("app.dashboard.components.death_mode_banner.st.markdown")
@patch("app.dashboard.components.trader_decision.st")
@patch("app.dashboard.components.trader_decision.PaperRepository")
def test_trader_decision_tab_displays_death_mode_banner(mock_repo_class, mock_st, mock_banner_markdown):
    """Verifies that render_trader_decision_tab surfaces the neon banner when equity is breached."""
    mock_repo = MagicMock()
    mock_repo.get_or_create_portfolio.return_value = {
        'initial_equity': 10000.0,
        'current_equity': 4500.0,
        'current_cash': 4500.0
    }
    mock_repo.get_open_positions.return_value = []
    mock_repo.get_recent_orders.return_value = []
    mock_repo.get_closed_positions.return_value = []
    mock_repo.get_equity_snapshots.return_value = []
    mock_repo_class.return_value = mock_repo

    mock_st.columns.side_effect = lambda x: [MagicMock() for _ in range(x)] if isinstance(x, int) else [MagicMock() for _ in range(len(x))]
    mock_st.button.return_value = False

    render_trader_decision_tab()

    markdown_calls = [call[0][0] for call in mock_banner_markdown.call_args_list if len(call[0]) > 0 and isinstance(call[0][0], str)]
    assert any("neon-death-banner" in content for content in markdown_calls)
