import re
from typing import Optional
from app.research.multi_timeframe.models import TimeframeHierarchy

class TimeframeValidator:
    """Validates timeframe strings and enforces HTF > MTF > LTF."""
    
    @staticmethod
    def _parse_minutes(tf: str) -> Optional[int]:
        if not tf:
            return None
        match = re.match(r"^(\d+)([a-zA-Z]+)$", tf.strip())
        if not match:
            return None
        val, unit = match.groups()
        val = int(val)
        unit = unit.lower()
        if unit in ["m", "min", "t"]:
            return val
        elif unit in ["h", "hr"]:
            return val * 60
        elif unit in ["d", "day"]:
            return val * 1440
        elif unit in ["w", "wk"]:
            return val * 10080
        return None

    @classmethod
    def validate_hierarchy(cls, hierarchy: TimeframeHierarchy) -> bool:
        htf_min = cls._parse_minutes(hierarchy.higher_timeframe)
        ltf_min = cls._parse_minutes(hierarchy.lower_timeframe)
        
        if not htf_min or not ltf_min:
            return False
            
        if hierarchy.middle_timeframe:
            mtf_min = cls._parse_minutes(hierarchy.middle_timeframe)
            if not mtf_min:
                return False
            if not (htf_min > mtf_min > ltf_min):
                return False
        else:
            if not (htf_min > ltf_min):
                return False
                
        return True
