from typing import Dict, List, Optional, Any
from app.diagnostics.models import RejectionReason, SignalAuditRecord
from app.config import config

class TelemetryTracker:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.enabled = getattr(config, 'DIAGNOSTIC_MODE', False)
        self.stage_counts = {
            "MARKET_BARS": 0,
            "STRATEGY_SIGNALS": 0,
            "ENSEMBLE_SIGNALS": 0,
            "RISK_APPROVED": 0,
            "PAPER_TRADES": 0
        }
        self.rejection_counts: Dict[RejectionReason, int] = {r: 0 for r in RejectionReason}
        self.regime_rejections: Dict[str, Dict[RejectionReason, int]] = {}
        self.audit_records: List[SignalAuditRecord] = []
        
        # Strategy specific diagnostics
        self.strategy_evaluations: Dict[str, int] = {}
        self.strategy_signals_long: Dict[str, int] = {}
        self.strategy_signals_short: Dict[str, int] = {}
        
        # Regime diagnostics
        self.regime_counts: Dict[str, int] = {}
        
        # Adaptive diagnostics
        self.adaptive_decisions: List[Dict[str, Any]] = []
        
    def record_stage(self, stage: str, count: int = 1):
        if self.enabled:
            self.stage_counts[stage] = self.stage_counts.get(stage, 0) + count
            
    def record_rejection(self, reason: RejectionReason, regime: Optional[str] = None):
        if self.enabled:
            self.rejection_counts[reason] += 1
            if regime:
                if regime not in self.regime_rejections:
                    self.regime_rejections[regime] = {r: 0 for r in RejectionReason}
                self.regime_rejections[regime][reason] += 1
            
    def record_audit(self, record: SignalAuditRecord):
        if self.enabled:
            self.audit_records.append(record)
            
    def record_strategy_eval(self, strategy_name: str, signal_dir: Optional[str]):
        if self.enabled:
            self.strategy_evaluations[strategy_name] = self.strategy_evaluations.get(strategy_name, 0) + 1
            if signal_dir == "LONG":
                self.strategy_signals_long[strategy_name] = self.strategy_signals_long.get(strategy_name, 0) + 1
            elif signal_dir == "SHORT":
                self.strategy_signals_short[strategy_name] = self.strategy_signals_short.get(strategy_name, 0) + 1
                
    def record_regime(self, regime: str):
        if self.enabled:
            self.regime_counts[regime] = self.regime_counts.get(regime, 0) + 1

    def record_adaptive_decision(self, regime: str, weights: Dict[str, float], confidence: str):
        if self.enabled:
            self.adaptive_decisions.append({
                "regime": regime,
                "weights": weights,
                "confidence": confidence
            })

    def export_snapshot(self) -> Dict[str, Any]:
        """Exports a deterministic, JSON-serializable snapshot of the current telemetry state."""
        return {
            "enabled": self.enabled,
            "stage_counts": dict(self.stage_counts),
            "rejection_counts": {k.value if hasattr(k, 'value') else str(k): v for k, v in self.rejection_counts.items()},
            "regime_rejections": {
                regime: {k.value if hasattr(k, 'value') else str(k): v for k, v in rej_dict.items()}
                for regime, rej_dict in self.regime_rejections.items()
            },
            "strategy_evaluations": dict(self.strategy_evaluations),
            "strategy_signals_long": dict(self.strategy_signals_long),
            "strategy_signals_short": dict(self.strategy_signals_short),
            "regime_counts": dict(self.regime_counts),
            "adaptive_decisions": list(self.adaptive_decisions)
        }

# Singleton
telemetry = TelemetryTracker()
