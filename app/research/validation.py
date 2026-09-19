from typing import List
from app.core.models import MarketBar
from app.research.models import ValidationResult

def validate_dataset(bars: List[MarketBar], symbol: str) -> ValidationResult:
    """
    Validates a dataset for chronological order, missing values, and impossible OHLC relationships.
    Does NOT mutate data.
    """
    errors = []
    warnings = []
    
    if not bars:
        return ValidationResult(is_valid=False, errors=["Empty dataset"], warnings=[], row_count=0, symbol=symbol)
        
    row_count = len(bars)
    
    if row_count < 100:
        errors.append(f"Insufficient data: only {row_count} bars available. Minimum 100 required.")
        
    seen_timestamps = set()
    prev_time = None
    
    for i, bar in enumerate(bars):
        # Timestamp checks
        if bar.timestamp in seen_timestamps:
            errors.append(f"Duplicate timestamp detected at index {i}: {bar.timestamp}")
        seen_timestamps.add(bar.timestamp)
        
        if prev_time and bar.timestamp <= prev_time:
            errors.append(f"Chronological ordering violation at index {i}: {bar.timestamp} <= {prev_time}")
            
        prev_time = bar.timestamp
        
        # OHLC logical checks
        if bar.high < bar.low:
            errors.append(f"Invalid OHLC: High ({bar.high}) < Low ({bar.low}) at index {i}")
        if bar.open > bar.high or bar.open < bar.low:
            errors.append(f"Invalid OHLC: Open not within High-Low range at index {i}")
        if bar.close > bar.high or bar.close < bar.low:
            errors.append(f"Invalid OHLC: Close not within High-Low range at index {i}")
            
        # Missing or negative checks
        if bar.volume < 0:
            errors.append(f"Invalid volume: Negative volume {bar.volume} at index {i}")
        if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
            errors.append(f"Invalid OHLC: Price <= 0 at index {i}")
            
    is_valid = len(errors) == 0
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        row_count=row_count,
        symbol=symbol
    )
