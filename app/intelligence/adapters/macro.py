from typing import List
from app.intelligence.models import WorldObservation

class MacroAdapter:
    """
    Adapter for Macro Economic data (Inflation, Rates, NFP).
    Currently returns NOT_AVAILABLE (empty list) because no legitimate 
    keyless public API is assumed present in this environment.
    We refuse to fabricate macro data.
    """
    
    def fetch_observations(self) -> List[WorldObservation]:
        # Status: NOT_AVAILABLE
        return []

class FlowAdapter:
    """
    Adapter for Institutional Flow data.
    Status: NOT_AVAILABLE
    """
    
    def fetch_observations(self) -> List[WorldObservation]:
        return []
