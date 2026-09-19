import logging
from typing import List, Dict, Callable
from datetime import datetime
from app.data.interfaces import HistoricalDataProvider
from app.core.models import MarketBar

logger = logging.getLogger(__name__)

class MarketScanner:
    """
    Basic Market Scanner that consumes historical data to filter symbols
    based on custom conditions.
    """
    
    def __init__(self, data_provider: HistoricalDataProvider):
        self.data_provider = data_provider
        
    def scan(
        self,
        symbols: List[str],
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        condition: Callable[[List[MarketBar]], bool]
    ) -> List[str]:
        """
        Scans a list of symbols and returns those that meet the specified condition.
        
        :param symbols: List of market symbols to scan (e.g., ['BTC/USD', 'ETH/USD'])
        :param timeframe: Timeframe to request from data provider (e.g., '1D', '1H')
        :param start_time: Start time for data fetch
        :param end_time: End time for data fetch
        :param condition: A callable that takes a list of MarketBars and returns True/False
        :return: List of symbols that evaluated to True for the condition
        """
        matched_symbols = []
        
        for symbol in symbols:
            try:
                # Fetch data
                bars = self.data_provider.get_historical_bars(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_time=start_time,
                    end_time=end_time
                )
                
                # If no data returned, skip
                if not bars:
                    logger.info("No data returned for %s, skipping.", symbol)
                    continue
                    
                # Evaluate condition
                if condition(bars):
                    matched_symbols.append(symbol)
                    
            except TimeoutError:
                logger.error("Market-data request timed out: symbol=%s", symbol)
                continue
            except ConnectionError:
                logger.error("Market-data connection failed: symbol=%s", symbol)
                continue
            except ValueError as ve:
                logger.error("Invalid market data for symbol=%s: %s", symbol, ve)
                continue
            except Exception as e:
                logger.exception("Unexpected market-data failure: symbol=%s error=%s", symbol, e)
                continue
                
        return matched_symbols

    def get_latest_close_prices(
        self, 
        symbols: List[str], 
        timeframe: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> Dict[str, float]:
        """
        A utility scan to just fetch the most recent closing price for a list of symbols.
        """
        latest_prices = {}
        for symbol in symbols:
            try:
                bars = self.data_provider.get_historical_bars(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_time=start_time,
                    end_time=end_time
                )
                if bars:
                    # Bars are ordered by timestamp by the provider
                    latest_prices[symbol] = bars[-1].close
            except TimeoutError:
                logger.error("Market-data request timed out: symbol=%s", symbol)
            except ConnectionError:
                logger.error("Market-data connection failed: symbol=%s", symbol)
            except Exception as e:
                logger.exception("Unexpected error fetching latest price: symbol=%s error=%s", symbol, e)
                
        return latest_prices
