from pydantic import BaseModel, Field
from typing import List, Optional, Protocol
from datetime import datetime
import hashlib
import json
from app.core.models import MarketBar

class ForecastResult(BaseModel):
    """The raw output from a ForecastModel."""
    predicted_values: List[float]
    prediction_interval_lower: Optional[List[float]] = None
    prediction_interval_upper: Optional[List[float]] = None

class ForecastModel(Protocol):
    """Protocol for forecasting models."""
    def predict(self, history: List[MarketBar], horizon: int) -> ForecastResult:
        ...
        
    @property
    def model_name(self) -> str:
        ...

class ForecastRecord(BaseModel):
    """Immutable representation of a persisted forecast."""
    forecast_id: str
    dataset_identity: str
    symbol: str
    timeframe: str
    
    input_start: datetime
    input_end: datetime
    forecast_start: datetime
    forecast_end: datetime
    
    model_name: str
    model_version: str
    
    window_size: int
    forecast_horizon: int
    
    predicted_values_json: str
    interval_lower_json: Optional[str] = None
    interval_upper_json: Optional[str] = None
    
    status: str = "GENERATED"
    
    mae: Optional[float] = None
    directional_accuracy: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_hash(self) -> str:
        data = f"{self.symbol}|{self.input_end.isoformat()}|{self.model_name}|{self.forecast_horizon}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
