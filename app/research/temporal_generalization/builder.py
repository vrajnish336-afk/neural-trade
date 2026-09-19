import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from app.research.temporal_generalization.models import WalkForwardWindow, WalkForwardType, WalkForwardWindowStatus

class WalkForwardWindowBuilder:
    def _hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def build_windows(self, run_id: str, candidate_id: str, dataset_identity: str,
                     full_start: datetime, full_end: datetime,
                     train_days: int, val_days: int, forward_days: int,
                     step_days: int, wf_type: WalkForwardType,
                     strategy_identity: str, parameter_identity: str,
                     as_of: datetime, lineage: str) -> List[WalkForwardWindow]:
        
        windows = []
        current_train_start = full_start
        window_index = 0
        
        while True:
            train_end = current_train_start + timedelta(days=train_days) if wf_type == WalkForwardType.ROLLING else full_start + timedelta(days=train_days + window_index * step_days)
            val_start = train_end # Can add purge gaps here if needed
            val_end = val_start + timedelta(days=val_days)
            fwd_start = val_end
            fwd_end = fwd_start + timedelta(days=forward_days)
            
            if fwd_end > full_end:
                break
                
            # Crucial: Enforce as_of lockout. We cannot create a window if its forward period exceeds the historical knowable barrier.
            if fwd_end > as_of:
                break
                
            w_id = self._hash(f"wf_{run_id}_{window_index}_{fwd_start.isoformat()}")
            
            w = WalkForwardWindow(
                window_id=w_id,
                run_id=run_id,
                candidate_id=candidate_id,
                dataset_identity=dataset_identity,
                train_start=full_start if wf_type == WalkForwardType.EXPANDING else current_train_start,
                train_end=train_end,
                validation_start=val_start,
                validation_end=val_end,
                forward_start=fwd_start,
                forward_end=fwd_end,
                methodology_version="wf_v1",
                strategy_identity=strategy_identity,
                parameter_identity=parameter_identity,
                status=WalkForwardWindowStatus.PENDING,
                as_of=as_of,
                created_at=datetime.now(timezone.utc),
                lineage=lineage
            )
            windows.append(w)
            
            current_train_start += timedelta(days=step_days)
            window_index += 1
            
        return windows
