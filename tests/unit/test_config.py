import pytest
import os
from unittest import mock
from app.config import Config

@pytest.fixture
def default_config():
    """Fixture that returns a fresh Config instance using default environment variables."""
    with mock.patch.dict(os.environ, {}, clear=True):
        return Config()

def test_configuration_defaults(default_config):
    """Test that default configuration values are safe and expected."""
    assert default_config.ENVIRONMENT == "development"
    assert default_config.PAPER_TRADING is True
    assert default_config.LIVE_TRADING is False
    assert default_config.LOG_LEVEL == "INFO"
    assert default_config.DATABASE_URL == "sqlite:///data/trading_bot.db"
    
def test_paper_trading_remains_enabled_by_default(default_config):
    """Explicitly verify paper trading is the default fallback."""
    assert default_config.PAPER_TRADING is True

def test_invalid_configuration():
    """Test that invalid config strings are safely parsed (e.g., boolean conversions)."""
    with mock.patch.dict(os.environ, {"LIVE_TRADING": "invalid", "PAPER_TRADING": "FALSE"}, clear=True):
        config = Config()
        assert config.LIVE_TRADING is False  # Any string other than 'true' is False
        assert config.PAPER_TRADING is False # Handled properly
