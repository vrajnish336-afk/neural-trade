import logging
from app.core.models import TradingSignal

logger = logging.getLogger(__name__)

def is_valid_signal(signal: TradingSignal) -> bool:
    """
    Validates the logical correctness of a trading signal.
    Does not fix invalid signals; safely rejects them.
    """
    try:
        if not signal.symbol or not signal.timestamp or not signal.strategy:
            return False
            
        if not signal.direction in ("LONG", "SHORT"):
            return False
            
        if not (0.0 <= signal.confidence <= 1.0):
            return False
            
        if signal.entry_price is not None and signal.entry_price <= 0:
            return False
            
        # Check logical placement of stop loss and take profit
        if signal.entry_price is not None:
            if signal.direction == "LONG":
                if signal.stop_loss is not None and signal.stop_loss >= signal.entry_price:
                    logger.warning("Invalid LONG signal: Stop loss must be below entry price.")
                    return False
                if signal.take_profit is not None and signal.take_profit <= signal.entry_price:
                    logger.warning("Invalid LONG signal: Take profit must be above entry price.")
                    return False
            elif signal.direction == "SHORT":
                if signal.stop_loss is not None and signal.stop_loss <= signal.entry_price:
                    logger.warning("Invalid SHORT signal: Stop loss must be above entry price.")
                    return False
                if signal.take_profit is not None and signal.take_profit >= signal.entry_price:
                    logger.warning("Invalid SHORT signal: Take profit must be below entry price.")
                    return False
                    
        return True
    except Exception as e:
        logger.exception("Signal validation encountered an unexpected error: %s", e)
        return False
