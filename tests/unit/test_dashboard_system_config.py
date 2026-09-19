import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from app.dashboard.components.system_config import render_system_config_tab
from app.config import config
from app.learning.paper_evolution_engine import SAFE_PARAMETERS

@patch("streamlit.markdown")
@patch("streamlit.warning")
@patch("streamlit.dataframe")
@patch("app.learning.paper_evolution_repository.PaperEvolutionRepository")
def test_system_config_renders_values(mock_repo, mock_dataframe, mock_warning, mock_markdown):
    # Setup some test state
    mock_instance = mock_repo.return_value
    mock_instance.get_lessons.return_value = []
    
    old_min = getattr(config, "MIN_SIGNAL_SCORE", None)
    config.MIN_SIGNAL_SCORE = 77.7
    config.TestStrategy_MIN_SCORE = 88.8
    
    render_system_config_tab()
    
    # Assert safety warning
    mock_warning.assert_any_call("READ-ONLY VIEW. PAPER TRADING ONLY. LIVE TRADING DISABLED.")
    
    # Check dataframes
    assert mock_dataframe.call_count == 3
    
    # Extract arguments passed to st.dataframe
    risk_df = mock_dataframe.call_args_list[0][0][0]
    strategy_df = mock_dataframe.call_args_list[1][0][0]
    allowlist_df = mock_dataframe.call_args_list[2][0][0]
    
    # Assert Risk DF contains PAPER_TRADING
    assert "PAPER_TRADING" in risk_df["Parameter"].values
    
    # Assert Strategy DF contains global and specific thresholds
    assert "Global MIN_SIGNAL_SCORE" in strategy_df["Parameter"].values
    assert strategy_df[strategy_df["Parameter"] == "Global MIN_SIGNAL_SCORE"]["Value"].iloc[0] == "77.7"
    
    assert "Strategy: TestStrategy" in strategy_df["Parameter"].values
    assert strategy_df[strategy_df["Parameter"] == "Strategy: TestStrategy"]["Value"].iloc[0] == "88.8"
    
    # Assert Allowlist DF
    assert "*_MIN_SCORE (Dynamic Strategy Thresholds)" in allowlist_df["Allowed Mutable Parameter"].values
    
    # Cleanup
    if old_min is not None:
        config.MIN_SIGNAL_SCORE = old_min
    delattr(config, "TestStrategy_MIN_SCORE")

@patch("streamlit.markdown")
@patch("streamlit.warning")
@patch("streamlit.dataframe")
@patch("app.learning.paper_evolution_repository.PaperEvolutionRepository")
def test_system_config_unavailable_fields(mock_repo, mock_dataframe, mock_warning, mock_markdown):
    # Setup some test state
    mock_instance = mock_repo.return_value
    mock_instance.get_lessons.return_value = []
    
    # Temporarily remove a field to trigger 'Unavailable'
    old_max = getattr(config, "MAX_POSITION_SIZE", None)
    if hasattr(config, "MAX_POSITION_SIZE"):
        delattr(config, "MAX_POSITION_SIZE")
        
    render_system_config_tab()
    
    risk_df = mock_dataframe.call_args_list[0][0][0]
    assert "MAX_POSITION_SIZE" in risk_df["Parameter"].values
    assert risk_df[risk_df["Parameter"] == "MAX_POSITION_SIZE"]["Value"].iloc[0] == "Unavailable"
    
    if old_max is not None:
        config.MAX_POSITION_SIZE = old_max

def test_system_config_is_readonly():
    # The component should not have any mutating API calls or return values
    with patch("streamlit.markdown"), patch("streamlit.warning"), patch("streamlit.dataframe"), patch("app.learning.paper_evolution_repository.PaperEvolutionRepository"):
        result = render_system_config_tab()
        assert result is None # It's a pure void render function

@patch("streamlit.markdown")
@patch("streamlit.warning")
@patch("streamlit.dataframe")
@patch("app.learning.paper_evolution_repository.PaperEvolutionRepository")
def test_system_config_shows_verified_strategies(mock_repo, mock_dataframe, mock_warning, mock_markdown):
    from app.learning.paper_evolution_models import LessonState
    
    # Mock a validated lesson
    mock_lesson = MagicMock()
    mock_lesson.strategy = "VerifiedTrend"
    mock_lesson.confidence_status = LessonState.VALIDATED
    
    # Mock a proposal
    mock_proposal = MagicMock()
    mock_proposal.affected_parameter = "Breakout_MIN_SCORE"
    
    mock_instance = mock_repo.return_value
    mock_instance.get_lessons.return_value = [mock_lesson]
    mock_instance.get_proposals.return_value = [mock_proposal]
    
    with patch.dict('os.environ', {'ENVSTRATEGY_MIN_SCORE': '99.0'}):
        render_system_config_tab()
    
    strategy_df = mock_dataframe.call_args_list[1][0][0]
    
    assert "Strategy: VerifiedTrend" in strategy_df["Parameter"].values
    assert "Strategy: Breakout" in strategy_df["Parameter"].values
    assert "Strategy: ENVSTRATEGY" in strategy_df["Parameter"].values
    
    assert strategy_df[strategy_df["Parameter"] == "Strategy: ENVSTRATEGY"]["Value"].iloc[0] == "99.0"

@patch("streamlit.markdown")
@patch("streamlit.warning")
@patch("streamlit.dataframe")
def test_system_config_discovers_multiple_strategies_from_dir(mock_dataframe, mock_warning, mock_markdown):
    # This test asserts that when multiple strategy keys exist on the config class, discovery renders them.
    from app.config import Config
    
    # Temporarily add class attributes
    setattr(Config, "TrendFollowing_MIN_SCORE", 65.0)
    setattr(Config, "Breakout_MIN_SCORE", 75.0)
    
    # Ensure they are NOT in instance __dict__ to prove dir() works
    render_system_config_tab()
    
    strategy_df = mock_dataframe.call_args_list[1][0][0]
    
    # Assert multiple strategies discovered
    assert "Strategy: TrendFollowing" in strategy_df["Parameter"].values
    assert "Strategy: Breakout" in strategy_df["Parameter"].values
    
    assert strategy_df[strategy_df["Parameter"] == "Strategy: TrendFollowing"]["Value"].iloc[0] == "65.0"
    assert strategy_df[strategy_df["Parameter"] == "Strategy: Breakout"]["Value"].iloc[0] == "75.0"
    
    delattr(Config, "TrendFollowing_MIN_SCORE")
    delattr(Config, "Breakout_MIN_SCORE")

@patch("streamlit.markdown")
@patch("streamlit.warning")
@patch("streamlit.dataframe")
@patch("app.learning.paper_evolution_repository.PaperEvolutionRepository")
def test_system_config_shows_base_strategies_when_no_overrides(mock_repo, mock_dataframe, mock_warning, mock_markdown):
    # This test reproduces the issue where discovery returns an empty set if no overrides or lessons exist
    mock_instance = mock_repo.return_value
    mock_instance.get_lessons.return_value = []
    mock_instance.get_proposals.return_value = []
    
    with patch.dict('os.environ', {}, clear=True):
        render_system_config_tab()
        
    strategy_df = mock_dataframe.call_args_list[1][0][0]
    
    # Assert base strategies are discovered even without overrides
    assert "Strategy: BreakoutStrategy" in strategy_df["Parameter"].values
    assert "Strategy: TrendFollowingStrategy" in strategy_df["Parameter"].values
    assert "Strategy: MeanReversionStrategy" in strategy_df["Parameter"].values
