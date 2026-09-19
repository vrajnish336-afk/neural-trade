import logging
import sys
from typing import Optional
from app.config import config

# Define custom SUCCESS level
SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")

def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)

logging.Logger.success = success

class CustomFormatter(logging.Formatter):
    def format(self, record):
        # We enforce the specific format required by the prompt
        # 2026-09-12 01:20:31 | [INFO] | scanner | Starting market scan
        time_str = self.formatTime(record, self.datefmt)
        level_name = f"[{record.levelname}]"
        return f"{time_str} | {level_name} | {record.name.split('.')[-1]} | {record.getMessage()}"

def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configures the root logger for the application.
    Secrets and sensitive data should never be logged.
    """
    level_str = log_level or getattr(config, "LOG_LEVEL", "INFO")
    level = getattr(logging, level_str.upper(), logging.INFO)
    
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Remove any existing handlers to prevent duplicates (e.g. during Streamlit reloads)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    formatter = CustomFormatter(datefmt="%Y-%m-%d %H:%M:%S")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info("Logging initialized at level %s", level_str)
    
