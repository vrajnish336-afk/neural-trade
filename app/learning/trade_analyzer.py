from typing import List, Dict, Any
from collections import defaultdict
import sqlite3
import json
import logging
from pydantic import BaseModel

from app.config import config
from app.research.forward_validation_models import ForwardDriftState

logger = logging.getLogger(__name__)

class RegimePerformance(BaseModel):
    identity_hash: str
    strategy: str
    regime: str
    observation_ids: List[str]
    win_count: int
    loss_count: int
    avg_pnl: float
    avg_drawdown: float

class TradeAnalyzer:
    """Deterministically extracts regime-based performance patterns from observations."""
    
    def analyze_candidate(self, identity_hash: str) -> List[RegimePerformance]:
        """Analyzes all available paper observations for a given candidate."""
        if not config.ENABLE_PERSISTENCE:
            return []
            
        observations = []
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT o.observation_id, o.net_pnl, o.drawdown_pct, o.regime_distribution_json, r.mapped_strategy
                    FROM paper_observations o
                    JOIN paper_track_records ptr ON o.track_record_id = ptr.track_record_id
                    JOIN research_memory r ON ptr.identity_hash = r.identity_hash
                    WHERE ptr.identity_hash = ?
                """, (identity_hash,))
                
                for row in cursor.fetchall():
                    regimes = json.loads(row[3]) if row[3] else {}
                    dominant_regime = None
                    if regimes:
                        dominant_regime = max(regimes.items(), key=lambda x: x[1])[0]
                        
                    observations.append({
                        "id": row[0],
                        "pnl": row[1],
                        "drawdown": row[2],
                        "regime": dominant_regime,
                        "strategy": row[4]
                    })
        except Exception as e:
            logger.error(f"Trade analysis failed: {e}")
            return []
            
        # Group by regime
        regime_groups = defaultdict(lambda: {"ids": [], "wins": 0, "losses": 0, "pnl_sum": 0.0, "dd_sum": 0.0, "strategy": ""})
        
        for obs in observations:
            reg = obs["regime"]
            if not reg: continue
            
            group = regime_groups[reg]
            group["ids"].append(obs["id"])
            if obs["pnl"] > 0:
                group["wins"] += 1
            else:
                group["losses"] += 1
            group["pnl_sum"] += obs["pnl"]
            group["dd_sum"] += obs["drawdown"]
            group["strategy"] = obs["strategy"]
            
        results = []
        for reg, group in regime_groups.items():
            total = len(group["ids"])
            results.append(RegimePerformance(
                identity_hash=identity_hash,
                strategy=group["strategy"],
                regime=reg,
                observation_ids=group["ids"],
                win_count=group["wins"],
                loss_count=group["losses"],
                avg_pnl=group["pnl_sum"] / total if total > 0 else 0,
                avg_drawdown=group["dd_sum"] / total if total > 0 else 0
            ))
            
        return results
