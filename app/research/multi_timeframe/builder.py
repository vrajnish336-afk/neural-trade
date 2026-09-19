import pandas as pd
from typing import List, Optional
from datetime import datetime

from app.core.models import MarketBar
from app.analysis.timeframes import resample_bars
from app.research.multi_timeframe.models import (
    TimeframeHierarchy, MultiTimeframeContext, TimeframeState, CandleStatus
)
from app.research.multi_timeframe.validator import TimeframeValidator

class MultiTimeframeContextBuilder:
    """
    Builds the context dynamically from LTF historical slices.
    Strictly excludes the currently forming (in-progress) higher timeframe candle
    to ensure zero look-ahead bias.
    """
    def __init__(self, hierarchy: TimeframeHierarchy, dataset_identity: str, as_of: datetime):
        if not TimeframeValidator.validate_hierarchy(hierarchy):
            raise ValueError(f"Invalid timeframe hierarchy: {hierarchy}")
        self.hierarchy = hierarchy
        self.dataset_identity = dataset_identity
        self.as_of = as_of

    def _get_last_completed(self, bars: List[MarketBar], tf_rule: str, current_ltf_timestamp: datetime) -> Optional[TimeframeState]:
        """
        Resamples up to the current LTF, but then specifically isolates the last
        candle whose physical end boundary is <= current_ltf_timestamp.
        Pandas resample with closed='left' sets the index to the START of the candle.
        """
        if not bars:
            return None
            
        tf_rule = tf_rule.replace('H', 'h').replace('D', 'd')
        df = resample_bars(bars, tf_rule)
        if df.empty:
            return None
            
        # The index of 'df' is the START time of the bucket.
        # We need to know the offset to compute the END time of the bucket.
        try:
            offset = pd.tseries.frequencies.to_offset(tf_rule)
        except Exception:
            return None
            
        # Find the latest candle whose END time is <= current_ltf_timestamp
        # i.e., it is fully closed and locked.
        valid_candles = []
        for start_time, row in df.iterrows():
            end_time = start_time + offset
            if end_time <= current_ltf_timestamp:
                valid_candles.append((start_time, row))
                
        if not valid_candles:
            return None
            
        last_start, last_row = valid_candles[-1]
        
        return TimeframeState(
            timeframe=tf_rule,
            timestamp=last_start, # We record the start boundary
            close=float(last_row['close']),
            status=CandleStatus.COMPLETED
        )

    def build_context(self, historical_slice: List[MarketBar]) -> Optional[MultiTimeframeContext]:
        if not historical_slice:
            return None
            
        current_ltf_bar = historical_slice[-1]
        current_ltf_timestamp = current_ltf_bar.timestamp
        
        # Check as_of
        if current_ltf_timestamp > self.as_of:
            return None
            
        ltf_state = TimeframeState(
            timeframe=self.hierarchy.lower_timeframe,
            timestamp=current_ltf_timestamp,
            close=current_ltf_bar.close,
            status=CandleStatus.COMPLETED
        )
        
        htf_state = self._get_last_completed(historical_slice, self.hierarchy.higher_timeframe, current_ltf_timestamp)
        if not htf_state:
            return None # HTF hasn't even completed one candle yet
            
        mtf_state = None
        if self.hierarchy.middle_timeframe:
            mtf_state = self._get_last_completed(historical_slice, self.hierarchy.middle_timeframe, current_ltf_timestamp)
            if not mtf_state:
                return None
                
        return MultiTimeframeContext(
            htf_state=htf_state,
            mtf_state=mtf_state,
            ltf_state=ltf_state,
            dataset_identity=self.dataset_identity,
            as_of=self.as_of
        )
