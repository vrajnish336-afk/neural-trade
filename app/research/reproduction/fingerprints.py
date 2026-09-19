import hashlib
import json
from typing import Dict, Any, List
from app.research.reproduction.models import ReproducedResearchOutput

class OutputFingerprintGenerator:
    
    @staticmethod
    def generate_fingerprint(
        trade_sequence: List[Dict[str, Any]],
        metrics: Dict[str, float],
        dataset_identity: str,
        methodology_version: str
    ) -> str:
        """
        Creates a canonical deterministic hash of structural research outputs.
        Excludes wall-clock time, random IDs, or any nondeterministic memory artifacts.
        """
        clean_trades = OutputFingerprintGenerator._canonicalize_trades(trade_sequence)
        
        # Round floats slightly to prevent 1e-12 micro-drifts from breaking fingerprints
        clean_metrics = {k: round(v, 8) for k, v in metrics.items()}
        
        payload = {
            "dataset": dataset_identity,
            "methodology": methodology_version,
            "metrics": clean_metrics,
            "trades": clean_trades
        }
        
        canonical_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        
    @staticmethod
    def _canonicalize_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clean = []
        for t in trades:
            # Only keep the structurally relevant parts (time, size, direction, price)
            ct = {
                "t": t.get("timestamp_str"),
                "d": t.get("direction"),
                "p": round(t.get("price", 0), 4),
                "s": round(t.get("size", 0), 6)
            }
            clean.append(ct)
        return clean
