import logging
import uuid
import json
import sqlite3
import traceback
from datetime import datetime, timezone
from typing import Optional, List

from app.config import config
from app.data.csv_provider import CsvHistoricalDataProvider
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.strategies.ensemble import StrategyEnsemble
from app.analytics.engine import generate_analytics_report

from app.research.models import ResearchExperiment
from app.research.evidence import ResearchEvidenceEvaluator
from app.research.forward_validation_models import (
    ForwardValidationRun, ForwardValidationState, FrozenSpecification, ForwardDriftState
)
from app.research.drift_analyzer import PerformanceDriftAnalyzer
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

class ForwardValidationService:
    """Orchestrates strict OOS / Forward Paper Validation for frozen candidate specifications."""
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = data_dir
        
    def _get_conn(self):
        return sqlite3.connect(config.DB_PATH)

    def _save_run(self, run: ForwardValidationRun) -> bool:
        if not config.ENABLE_PERSISTENCE: return False
        try:
            with self._get_conn() as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO forward_validation_runs 
                       (validation_id, identity_hash, reference_experiment_id, 
                        frozen_specification_json, dataset_identity_json, 
                        forward_start, forward_end, state, created_at, started_at, 
                        completed_at, result_experiment_id, failure_reason, drift_state)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        run.validation_id, run.identity_hash, run.reference_experiment_id,
                        run.frozen_specification.model_dump_json(),
                        json.dumps(run.dataset_identity) if run.dataset_identity else None,
                        run.forward_start.isoformat() if run.forward_start else None,
                        run.forward_end.isoformat() if run.forward_end else None,
                        run.state.value, run.created_at.isoformat(),
                        run.started_at.isoformat() if run.started_at else None,
                        run.completed_at.isoformat() if run.completed_at else None,
                        run.result_experiment_id, run.failure_reason,
                        run.drift_state.value if run.drift_state else None
                    )
                )
            return True
        except Exception as e:
            logger.error("Failed to save forward validation run: %s", e)
            return False

    def create_validation_request(self, identity_hash: str, reference_experiment_id: str, frozen_spec: FrozenSpecification) -> Optional[ForwardValidationRun]:
        """Creates a forward validation run, enforcing duplicate prevention."""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                # Check for existing run for this exact frozen spec
                frozen_hash = frozen_spec.get_hash()
                cursor.execute("""
                    SELECT validation_id FROM forward_validation_runs 
                    WHERE identity_hash = ? AND state IN ('CREATED', 'RUNNING', 'COMPLETED')
                """, (identity_hash,))
                # We do a loose check here for simplicity: only 1 active forward validation per identity is allowed at a time
                if cursor.fetchone():
                    logger.warning(f"Forward validation already exists or is running for identity {identity_hash}")
                    return None
                    
            run = ForwardValidationRun(
                validation_id=str(uuid.uuid4()),
                identity_hash=identity_hash,
                reference_experiment_id=reference_experiment_id,
                frozen_specification=frozen_spec
            )
            if self._save_run(run):
                telemetry.record_stage("FORWARD_VALIDATION_CREATED")
                return run
        except Exception as e:
            logger.error("Error creating validation request: %s", e)
        return None
        
    def _fail_run(self, run: ForwardValidationRun, reason: str, state: ForwardValidationState = ForwardValidationState.FAILED):
        run.state = state
        run.failure_reason = reason
        run.completed_at = datetime.utcnow()
        self._save_run(run)
        telemetry.record_stage("FORWARD_VALIDATION_FAILED")
        
    def execute_validation(self, run: ForwardValidationRun):
        """Executes the validation by strictly slicing data after the historical_end boundary."""
        run.state = ForwardValidationState.RUNNING
        run.started_at = datetime.utcnow()
        self._save_run(run)
        telemetry.record_stage("FORWARD_VALIDATION_STARTED")
        
        try:
            # 1. Load Data
            provider = CsvHistoricalDataProvider(self.data_dir)
            bars = []
            
            # CRITICAL SCIENTIFIC INTEGRITY STEP:
            # We enforce that the dataset ONLY contains records strictly strictly > historical_end
            boundary_time = run.frozen_specification.historical_end
            if boundary_time.tzinfo is None:
                boundary_time = boundary_time.replace(tzinfo=timezone.utc)
                
            for sym in run.frozen_specification.symbols:
                try:
                    sym_bars = provider.get_historical_bars(sym, run.frozen_specification.timeframe, boundary_time)
                    # Ensure strict greater-than to prevent boundary overlap
                    sym_bars = [b for b in sym_bars if b.timestamp > boundary_time]
                    bars.extend(sym_bars)
                except Exception:
                    logger.warning("No data for symbol %s", sym)
                    
            if not bars:
                self._fail_run(run, "No forward data available after historical boundary.", ForwardValidationState.INSUFFICIENT_DATA)
                return
                
            bars.sort(key=lambda x: x.timestamp)
            run.forward_start = bars[0].timestamp
            run.forward_end = bars[-1].timestamp
            
            # Require at least some minimal data for a valid run (e.g., 30 bars)
            if len(bars) < 30:
                self._fail_run(run, f"Insufficient forward data depth ({len(bars)} bars).", ForwardValidationState.INSUFFICIENT_DATA)
                return
                
            run.dataset_identity = {
                "source": self.data_dir,
                "start": run.forward_start.isoformat(),
                "end": run.forward_end.isoformat(),
                "row_count": len(bars)
            }
            
            # 2. Reconstruct Frozen Engine
            spec = run.frozen_specification
            strategy = None
            if spec.strategy == "TrendFollowing":
                from app.strategies.trend_following import TrendFollowingStrategy
                strategy = TrendFollowingStrategy()
            elif spec.strategy == "MeanReversion":
                from app.strategies.mean_reversion import MeanReversionStrategy
                strategy = MeanReversionStrategy()
            elif spec.strategy == "Breakout":
                from app.strategies.breakout import BreakoutStrategy
                strategy = BreakoutStrategy()
                
            if not strategy:
                self._fail_run(run, f"Mapped strategy {spec.strategy} is invalid.", ForwardValidationState.FAILED)
                return
                
            ensemble = StrategyEnsemble([strategy])
            risk_engine = RiskEngine(PortfolioRiskLimits())
            cost_config = CostConfig(
                commission_rate=spec.cost_config.get("commission_rate", 0.001), 
                slippage_rate=spec.cost_config.get("slippage_rate", 0.0005)
            )
            
            engine = BacktestEngine(
                ensemble=ensemble,
                risk_engine=risk_engine,
                initial_capital=spec.starting_capital,
                cost_config=cost_config
            )
            
            # 3. Execution (Chronological)
            result = engine.run(bars)
            
            analytics_report = generate_analytics_report(run.validation_id, result)
            
            # 4. Wrap as Experiment
            experiment = ResearchExperiment(
                experiment_id=str(uuid.uuid4()),
                experiment_name=f"Forward Validation: {run.validation_id}",
                dataset_id="local_csv_forward",
                dataset_identity=run.dataset_identity,
                symbols=spec.symbols,
                timeframe=spec.timeframe,
                strategy=spec.strategy,
                configuration=spec.configuration,
                starting_capital=spec.starting_capital,
                random_seed=spec.random_seed,
                created_at=datetime.utcnow(),
                status="COMPLETED",
                validation_results=[],
                out_of_sample_report=analytics_report
            )
            
            # 5. Drift Analysis
            # To compute drift, we need the historical result
            hist_result = None
            try:
                with self._get_conn() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT experiment_json FROM research_experiments WHERE id = ?", (run.reference_experiment_id,))
                    row = cursor.fetchone()
                    if row:
                        hist_exp_dict = json.loads(row[0])
                        # The metrics are in out_of_sample_report -> equity_metrics and trade_metrics
                        # We can construct a dummy BacktestResult just with the required drift metrics
                        report = hist_exp_dict.get("out_of_sample_report", {})
                        t_mets = report.get("trade_metrics", {})
                        # Fake a result object
                        from app.backtesting.models import BacktestResult
                        hist_result = BacktestResult(
                            initial_capital=10000.0,
                            final_equity=10000.0,
                            total_return_pct=0.0,
                            number_of_trades=t_mets.get("total_trades", 0),
                            winning_trades=t_mets.get("winning_trades", 0),
                            losing_trades=t_mets.get("losing_trades", 0),
                            win_rate=t_mets.get("win_rate_pct", 0.0),
                            gross_profit=t_mets.get("gross_profit", 0.0),
                            gross_loss=abs(t_mets.get("gross_loss", 0.0)),
                            net_profit=t_mets.get("net_profit", 0.0),
                            max_drawdown_pct=0.0,
                            average_trade_result=t_mets.get("average_trade_net", 0.0),
                            profit_factor=t_mets.get("profit_factor", 0.0),
                            average_holding_period_hours=0.0,
                            trades=[],
                            telemetry_snapshot={}
                        )
            except Exception as e:
                logger.error("Failed to load historical experiment for drift comparison: %s", e)
                
            if hist_result:
                run.drift_state = PerformanceDriftAnalyzer.analyze(hist_result, result)
            else:
                run.drift_state = ForwardDriftState.UNRESOLVED
                
            # 6. Evaluate Evidence (Treat it exactly as new evidence!)
            # We inject the new experiment into the evidence pool and save it
            summary = ResearchEvidenceEvaluator.evaluate(experiment)
            try:
                with self._get_conn() as conn:
                    conn.execute("INSERT OR REPLACE INTO research_experiments (id, timestamp, experiment_json) VALUES (?, ?, ?)",
                                 (experiment.experiment_id, experiment.created_at.isoformat(), experiment.model_dump_json()))
            except Exception:
                pass
                
            # Note: The existing ResearchDecisionEngine will be manually run or cron'd to pick up this new experiment
            # along with the historical ones.
            
            run.result_experiment_id = experiment.experiment_id
            run.state = ForwardValidationState.COMPLETED
            run.completed_at = datetime.utcnow()
            self._save_run(run)
            telemetry.record_stage("FORWARD_VALIDATION_COMPLETED")
            
        except Exception as e:
            logger.error("Error executing forward validation: %s\n%s", e, traceback.format_exc())
            self._fail_run(run, str(e), ForwardValidationState.FAILED)

    def recover_runs(self):
        """Fails runs that were interrupted."""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT validation_id FROM forward_validation_runs WHERE state = 'RUNNING'")
                rows = cursor.fetchall()
                for r in rows:
                    run = self.get_run(r[0])
                    if run:
                        self._fail_run(run, "Interrupted during execution.", ForwardValidationState.FAILED)
        except Exception as e:
            logger.error("Failed to recover validation runs: %s", e)
            
    def get_run(self, validation_id: str) -> Optional[ForwardValidationRun]:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM forward_validation_runs WHERE validation_id = ?", (validation_id,))
                row = cursor.fetchone()
                if row:
                    frozen_dict = json.loads(row[3])
                    spec = FrozenSpecification(**frozen_dict)
                    return ForwardValidationRun(
                        validation_id=row[0],
                        identity_hash=row[1],
                        reference_experiment_id=row[2],
                        frozen_specification=spec,
                        dataset_identity=json.loads(row[4]) if row[4] else None,
                        forward_start=datetime.fromisoformat(row[5]) if row[5] else None,
                        forward_end=datetime.fromisoformat(row[6]) if row[6] else None,
                        state=ForwardValidationState(row[7]),
                        created_at=datetime.fromisoformat(row[8]),
                        started_at=datetime.fromisoformat(row[9]) if row[9] else None,
                        completed_at=datetime.fromisoformat(row[10]) if row[10] else None,
                        result_experiment_id=row[11],
                        failure_reason=row[12],
                        drift_state=ForwardDriftState(row[13]) if row[13] else None
                    )
        except Exception as e:
            logger.error("Failed to fetch run: %s", e)
        return None
