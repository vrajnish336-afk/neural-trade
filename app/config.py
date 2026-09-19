import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

class Config:
    """Application configuration."""
    
    def __init__(self):
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        
        # Safety flags
        # Paper trading is enabled by default in development
        self.PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "true").lower() == "true"
        
        # LIVE_TRADING must be explicitly set to 'true' to even be considered.
        # The safety layer will further validate if live trading is actually permitted.
        self.LIVE_TRADING: bool = os.getenv("LIVE_TRADING", "false").lower() == "true"
        
        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/trading_bot.db")
        
        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        
        # Backtesting & Research Defaults
        self.DEFAULT_INITIAL_CAPITAL: float = float(os.getenv("DEFAULT_INITIAL_CAPITAL", "10000.0"))
        self.COMMISSION_RATE: float = float(os.getenv("COMMISSION_RATE", "0.001")) # 0.1%
        self.SLIPPAGE_RATE: float = float(os.getenv("SLIPPAGE_RATE", "0.0005")) # 0.05%
        
        # Risk Management
        self.MAX_POSITION_SIZE: float = float(os.getenv("MAX_POSITION_SIZE", "1.0")) # 100% of capital
        self.RISK_PER_TRADE: float = float(os.getenv("RISK_PER_TRADE", "0.01")) # 1%
        self.ATR_MULTIPLIER: float = float(os.getenv("ATR_MULTIPLIER", "2.0"))
        self.MAX_POSITIONS: int = int(os.getenv("MAX_POSITIONS", "5"))
        self.DAILY_LOSS_LIMIT: float = float(os.getenv("DAILY_LOSS_LIMIT", "0.05")) # 5% max daily loss
        self.LOSS_STREAK_THRESHOLD: int = int(os.getenv("LOSS_STREAK_THRESHOLD", "3"))
        self.COOLDOWN_BARS: int = int(os.getenv("COOLDOWN_BARS", "5"))
        
        # Ensemble & Signal
        self.MIN_SIGNAL_SCORE: float = float(os.getenv("MIN_SIGNAL_SCORE", "50.0"))
        
        # Persistence & Database
        self.ENABLE_PERSISTENCE: bool = os.getenv("ENABLE_PERSISTENCE", "True").lower() in ("true", "1", "yes")
        self.DB_PATH: str = os.getenv("DB_PATH", "data/backtests.sqlite")
        
        # Phase 8 Diagnostics
        self.DIAGNOSTIC_MODE: bool = os.getenv("DIAGNOSTIC_MODE", "false").lower() in ("true", "1", "yes")
        
        # Market Intelligence & News
        self.NEWS_LOOKBACK_HOURS: int = int(os.getenv("NEWS_LOOKBACK_HOURS", "72"))
        self.ANOMALY_ZSCORE_THRESHOLD: float = float(os.getenv("ANOMALY_ZSCORE_THRESHOLD", "2.5"))
        self.MIN_ARTICLE_RELEVANCE: float = float(os.getenv("MIN_ARTICLE_RELEVANCE", "0.5"))
        
        # News Ingestion
        self.NEWS_FEEDS: list[str] = os.getenv("NEWS_FEEDS", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,GOOG,AMZN,META").split(";")
        self.NEWS_FETCH_TIMEOUT: int = int(os.getenv("NEWS_FETCH_TIMEOUT", "10"))
        self.NEWS_MAX_RESPONSE_SIZE: int = int(os.getenv("NEWS_MAX_RESPONSE_SIZE", "5242880")) # 5MB limit
        
    def get_strategy_min_score(self, strategy_name: str) -> float:
        attr_name = f"{strategy_name}_MIN_SCORE"
        if hasattr(self, attr_name):
            return float(getattr(self, attr_name))
        return self.MIN_SIGNAL_SCORE

config = Config()

