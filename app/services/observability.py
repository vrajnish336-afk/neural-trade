import json
from typing import Dict, Any, Optional
from app.analytics.models import FullAnalyticsReport
from app.research.models import ResearchExperiment

class ObservabilityService:
    @staticmethod
    def get_analytics_report(run_id: str) -> Optional[FullAnalyticsReport]:
        import sqlite3
        from app.config import config
        try:
            conn = sqlite3.connect(config.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT report_json FROM analytics_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                data = json.loads(row[0])
                return FullAnalyticsReport(**data)
        except Exception:
            pass
        return None
        
    @staticmethod
    def get_experiment(experiment_id: str) -> Optional[ResearchExperiment]:
        import sqlite3
        from app.config import config
        try:
            conn = sqlite3.connect(config.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT experiment_json FROM research_experiments WHERE id = ?", (experiment_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                data = json.loads(row[0])
                return ResearchExperiment(**data)
        except Exception:
            pass
        return None

    @staticmethod
    def format_funnel(report: FullAnalyticsReport) -> str:
        telemetry = report.telemetry_snapshot
        if not telemetry:
            return "Telemetry data is not available for this run (Legacy Record)."
            
        stages = telemetry.get('stage_counts', {})
        rejections = telemetry.get('rejection_counts', {})
        
        funnel = [
            f"Market Bars: {stages.get('MARKET_BARS', 'N/A')}",
            "      ↓",
            f"Strategy Signals: {stages.get('STRATEGY_SIGNALS', 'N/A')}",
            "      ↓",
            f"Ensemble Signals: {stages.get('ENSEMBLE_SIGNALS', 'N/A')}",
            "      ↓",
            f"Risk Approved: {stages.get('RISK_APPROVED', 'N/A')}",
            "      ↓",
            f"Trades Executed: {stages.get('PAPER_TRADES', 'N/A')}"
        ]
        
        funnel.append("\n--- Rejection Breakdown ---")
        sorted_rejections = sorted(rejections.items(), key=lambda x: x[1], reverse=True)
        for reason, count in sorted_rejections:
            if count > 0:
                funnel.append(f"{reason}: {count}")
                
        return "\n".join(funnel)

    @staticmethod
    def format_friction(report: FullAnalyticsReport) -> str:
        tm = report.trade_metrics
        return (
            f"Gross PnL: ${tm.gross_pnl:.2f}\n"
            f"Total Commission: ${tm.total_commission:.2f}\n"
            f"Total Slippage: ${tm.total_slippage:.2f}\n"
            f"Net PnL: ${tm.net_pnl:.2f}\n"
        )
        
    @staticmethod
    def format_regimes(report: FullAnalyticsReport) -> str:
        if not report.regime_attribution:
            return "No regime data available."
            
        lines = []
        for attr in report.regime_attribution:
            lines.append(f"Regime: {attr.label}")
            lines.append(f"  Trades: {attr.sample_size}")
            lines.append(f"  Win Rate: {attr.win_rate:.2f}%")
            lines.append(f"  Net PnL: ${attr.total_pnl:.2f}")
            lines.append(f"  Profit Factor: {attr.profit_factor:.2f}")
            lines.append("")
        return "\n".join(lines).strip()
        
    @staticmethod
    def validate_comparison(exp1: ResearchExperiment, exp2: ResearchExperiment) -> tuple[bool, str]:
        # Identity match logic
        id1 = exp1.dataset_identity.get('hash') if isinstance(exp1.dataset_identity, dict) else exp1.dataset_identity
        id2 = exp2.dataset_identity.get('hash') if isinstance(exp2.dataset_identity, dict) else exp2.dataset_identity
        
        if id1 != id2:
            return False, f"Dataset Identity Mismatch: {id1} vs {id2}"
            
        seed1 = exp1.random_seed
        seed2 = exp2.random_seed
        if seed1 != seed2:
            return False, f"Random Seed Mismatch: {seed1} vs {seed2}"
            
        return True, "Identity Match"
