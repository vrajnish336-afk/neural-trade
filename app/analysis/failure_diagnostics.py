from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from app.backtesting.models import BacktestTrade

class FailureDiagnosticEngine:
    """
    Deterministically diagnoses failures across completed trades.
    Only uses entry-time features (recorded at time T) mapped to post-close outcomes (recorded at time T+X).
    """
    def __init__(self, closed_trades: List[BacktestTrade]):
        self.trades = closed_trades
        self._df = self._build_dataframe()
        
    def _build_dataframe(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
            
        data = []
        for t in self.trades:
            # Strategies may be CSV string or raw string
            strategies = t.strategies if t.strategies else "UNKNOWN"
            score = t.score if t.score is not None else 50.0
            
            data.append({
                "symbol": t.symbol,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "strategy": strategies,
                "regime": t.regime if t.regime else "UNKNOWN",
                "direction": t.direction,
                "score": score,
                "score_bucket": self._get_score_bucket(score),
                "fakeout_risk": t.fakeout_risk,
                "pnl": t.realized_pnl,
                "is_win": t.realized_pnl > 0,
                "exit_reason": t.exit_reason
            })
        return pd.DataFrame(data)
        
    def _get_score_bucket(self, score: float) -> str:
        if score < 20: return "0-19"
        elif score < 40: return "20-39"
        elif score < 60: return "40-59"
        elif score < 80: return "60-79"
        else: return "80-100"
        
    def get_regime_failure_matrix(self) -> List[Dict[str, Any]]:
        """
        Strategy x Regime historical evidence matrix.
        """
        if self._df.empty:
            return []
            
        grouped = self._df.groupby(["strategy", "regime"])
        results = []
        
        for (strategy, regime), group in grouped:
            count = len(group)
            wins = group['is_win'].sum()
            losses = count - wins
            win_rate = (wins / count) * 100 if count > 0 else 0
            
            pnl_wins = group[group['is_win']]['pnl'].sum()
            pnl_losses = abs(group[~group['is_win']]['pnl'].sum())
            pf = pnl_wins / pnl_losses if pnl_losses > 0 else float('inf')
            if pnl_wins == 0 and pnl_losses == 0: pf = 0.0
            
            avg_pnl = group['pnl'].mean()
            median_pnl = group['pnl'].median()
            avg_score = group['score'].mean()
            
            # Classification
            if count < 5:
                sample_class = "VERY_LOW_SAMPLE"
            elif count < 15:
                sample_class = "LOW_SAMPLE"
            elif count < 30:
                sample_class = "MODERATE_SAMPLE"
            else:
                sample_class = "SUFFICIENT_SAMPLE"
                
            status = "INSUFFICIENT_DATA"
            if count >= 15:
                if win_rate > 55 and pf > 1.2:
                    status = "BEST_HISTORICAL" if win_rate > 65 and pf > 1.5 else "ACCEPTABLE"
                else:
                    status = "WEAK"
            
            results.append({
                "strategy": strategy,
                "regime": regime,
                "sample_count": int(count),
                "wins": int(wins),
                "losses": int(losses),
                "win_rate": float(win_rate),
                "average_pnl": float(avg_pnl),
                "median_pnl": float(median_pnl),
                "profit_factor": float(pf),
                "average_score": float(avg_score),
                "sample_classification": sample_class,
                "quality_status": status
            })
            
        return results

    def get_signal_score_analysis(self) -> List[Dict[str, Any]]:
        """
        Investigate whether signal score actually separates outcomes.
        """
        if self._df.empty:
            return []
            
        grouped = self._df.groupby("score_bucket")
        results = []
        
        for bucket, group in grouped:
            count = len(group)
            wins = group['is_win'].sum()
            win_rate = (wins / count) * 100 if count > 0 else 0
            
            pnl_wins = group[group['is_win']]['pnl'].sum()
            pnl_losses = abs(group[~group['is_win']]['pnl'].sum())
            pf = pnl_wins / pnl_losses if pnl_losses > 0 else float('inf')
            
            avg_pnl = group['pnl'].mean()
            
            results.append({
                "score_bucket": bucket,
                "trade_count": int(count),
                "win_rate": float(win_rate),
                "average_pnl": float(avg_pnl),
                "profit_factor": float(pf)
            })
            
        return sorted(results, key=lambda x: x["score_bucket"])
        
    def diagnose_trending_up(self) -> Dict[str, Any]:
        """
        Specifically diagnose TRENDING_UP failures.
        """
        if self._df.empty:
            return {"status": "NO_DATA"}
            
        tu_df = self._df[self._df['regime'] == "TRENDING_UP"]
        if tu_df.empty:
            return {"status": "NO_TRADES_IN_REGIME"}
            
        total = len(tu_df)
        losses = tu_df[~tu_df['is_win']]
        
        loss_by_strategy = losses.groupby("strategy").size().to_dict()
        loss_by_direction = losses.groupby("direction").size().to_dict()
        loss_by_reason = losses.groupby("exit_reason").size().to_dict()
        
        return {
            "status": "DIAGNOSED",
            "total_trades": int(total),
            "loss_count": len(losses),
            "loss_by_strategy": {str(k): int(v) for k, v in loss_by_strategy.items()},
            "loss_by_direction": {str(k): int(v) for k, v in loss_by_direction.items()},
            "loss_by_exit_reason": {str(k): int(v) for k, v in loss_by_reason.items()},
            "conclusion": "Observed loss concentration in specific exit reasons." if len(losses) > 0 else "No losses observed."
        }
