from dataclasses import dataclass, field
from typing import List
import torch

@dataclass
class KronosConfig:
    """Configuration specific to the Kronos research engine."""
    
    # Model configuration
    model_name: str = "NeoQuasar/Kronos-small"
    tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-base"
    
    # Automatically uses CUDA if available, fulfilling requirement for CUDA/CPU fallback
    device: str = "cuda:0" if torch.cuda.is_available() else "cpu"
    
    # Context and prediction horizons
    lookback: int = 512
    prediction_horizon: int = 1
    
    # Research thresholds
    thresholds: List[float] = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 1.00])
    
    # Walk-forward configuration (number of bars)
    wf_train_size: int = 60
    wf_test_size: int = 20
    wf_step_size: int = 20

kronos_config = KronosConfig()
