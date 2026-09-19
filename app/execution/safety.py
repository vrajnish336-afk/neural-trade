import logging
from app.config import config

logger = logging.getLogger(__name__)

class ExecutionSafetyError(Exception):
    """Exception raised when a safety violation occurs in execution."""
    pass

class ExecutionSafetyGate:
    """
    Safety mechanism to ensure live trading cannot be enabled accidentally.
    This acts as a strict firewall between the logic and actual broker execution.
    """
    
    @staticmethod
    def is_live_trading_allowed() -> bool:
        """
        Determines whether actual live money trading is currently permitted.
        
        The safe default is ALWAYS False.
        Even if configuration requests live trading, strict conditions must be met.
        """
        if config.ENVIRONMENT.lower() != "production":
            logger.warning("Live trading rejected: Not in production environment.")
            return False
            
        if config.PAPER_TRADING is True:
            logger.warning("Live trading rejected: Paper trading is explicitly enabled.")
            return False
            
        if config.LIVE_TRADING is not True:
            logger.warning("Live trading rejected: LIVE_TRADING flag is not enabled.")
            return False
            
        # At this phase, we enforce a strict hard-coded false to guarantee safety.
        # Once actual broker execution code is written, this hard-coded block can 
        # be carefully replaced with runtime checks for valid API credentials and limits.
        logger.error("Live trading rejected: System is not yet cleared for live broker execution.")
        return False
        
    @staticmethod
    def is_paper_trading_allowed() -> bool:
        """
        Determines if paper trading (simulated execution) is allowed.
        """
        if config.PAPER_TRADING is True:
            return True
            
        # If paper trading is false but live trading is also not permitted,
        # the system effectively cannot execute any orders.
        return False
        
    @staticmethod
    def assert_safe_for_live_order() -> None:
        """
        Strict check to call immediately before placing any real order.
        Raises an exception if safety conditions fail.
        """
        if not ExecutionSafetyGate.is_live_trading_allowed():
            raise ExecutionSafetyError(
                "CRITICAL: Attempted to place a live order when live trading is not permitted!"
            )
