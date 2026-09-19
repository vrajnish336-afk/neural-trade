import argparse
import json
import logging
from pathlib import Path

from app.config import config
from app.database.schema import init_db
from app.research.experiments import run_governed_experiment
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.services.intelligence import IntelligenceService
from app.news.provider import FixtureNewsProvider
from app.cli.commands.helpers import get_strategy_class, setup_cli_logging

logger = logging.getLogger(__name__)

def setup_research_parser(subparsers):
    parser = subparsers.add_parser("research", help="Run a governed research experiment")
    parser.add_argument("--name", required=True, help="Name of the experiment")
    parser.add_argument("--strategy", required=True, choices=["breakout", "trend_following", "mean_reversion"], help="Strategy to run")
    parser.add_argument("--symbols", default="TEST", help="Comma-separated symbols")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output-json", help="Path to save output JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress logging")
    parser.set_defaults(func=run_research)

def run_research(args: argparse.Namespace) -> int:
    setup_cli_logging(args.quiet)
    init_db()

    symbols = [s.strip() for s in args.symbols.split(",")]
    
    strat_cls = get_strategy_class(args.strategy)
    
    def engine_factory(base_cost: CostConfig) -> BacktestEngine:
        strategy = strat_cls()
        ensemble = StrategyEnsemble([strategy], min_score=0.0)
        limits = PortfolioRiskLimits(initial_equity=10000.0)
        risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
        news_provider = FixtureNewsProvider()
        intel_service = IntelligenceService(news_provider=news_provider, config=config)
        return BacktestEngine(
            ensemble=ensemble,
            risk_engine=risk_engine,
            intelligence_service=intel_service,
            initial_capital=10000.0,
            cost_config=base_cost
        )
        
    base_cost = CostConfig(
        commission_rate=config.COMMISSION_RATE,
        slippage_rate=config.SLIPPAGE_RATE
    )
    
    # Capture Execution Lineage
    import sys
    import platform
    import subprocess
    from app.research.models import ResearchLineage, EnvironmentLineage, CodeLineage, StrategyLineage, ConfigurationLineage
    
    commit_hash = None
    is_dirty = None
    try:
        commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        dirty_status = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        is_dirty = len(dirty_status) > 0
    except Exception:
        pass
        
    env_lineage = EnvironmentLineage(python_version=sys.version.split(" ")[0], os_name=platform.system())
    code_lineage = CodeLineage(commit_hash=commit_hash, is_dirty=is_dirty)
    
    temp_strategy = strat_cls()
    strat_params = temp_strategy.get_parameters() if hasattr(temp_strategy, 'get_parameters') else {}
    strat_lineage = StrategyLineage(strategy_name=args.strategy, parameters=strat_params)
    
    config_lineage = ConfigurationLineage(
        cost_model={"commission_rate": base_cost.commission_rate, "slippage_rate": base_cost.slippage_rate},
        risk_model={"risk_per_trade_pct": 0.05},
        capital=10000.0
    )
    
    lineage = ResearchLineage(
        environment=env_lineage,
        code=code_lineage,
        strategy=strat_lineage,
        configuration=config_lineage
    )
    
    try:
        exp = run_governed_experiment(
            experiment_name=args.name,
            symbols=symbols,
            seed=args.seed,
            engine_factory=engine_factory,
            base_cost=base_cost,
            strategy_name=args.strategy,
            config_snapshot={"seed": args.seed, "symbols": symbols},
            lineage=lineage
        )
        
        # Output printing
        print("================================================")
        print("NEURAL TRADE — GOVERNED RESEARCH")
        print("================================================")
        print("\nMODE: RESEARCH ONLY")
        print("LIVE TRADING: DISABLED\n")
        print(f"Experiment: {args.name}")
        print(f"Strategy: {args.strategy}")
        print(f"Symbols: {args.symbols}")
        print(f"Seed: {args.seed}")
        print(f"Dataset Identity: {exp.dataset_identity.get('hash', 'N/A') if isinstance(exp.dataset_identity, dict) else 'N/A'}\n")
        
        print("---------------- RESULTS ----------------\n")
        print(f"Classification: {exp.classification}")
        
        wf_results = exp.walk_forward_results
        if wf_results:
            wf = wf_results[0]
            train_tm = wf.train_report.trade_metrics
            val_tm = wf.validation_report.trade_metrics
            print(f"Train Metrics: Win Rate {train_tm.win_rate:.2f}%, PF {train_tm.profit_factor:.2f}")
            print(f"Validation Metrics: Win Rate {val_tm.win_rate:.2f}%, PF {val_tm.profit_factor:.2f}")
        else:
            print("Train Metrics: N/A")
            print("Validation Metrics: N/A")
            
        if exp.out_of_sample_report:
            oos_tm = exp.out_of_sample_report.trade_metrics
            print(f"OOS/Test Metrics: Win Rate {oos_tm.win_rate:.2f}%, PF {oos_tm.profit_factor:.2f}")
        else:
            print("OOS/Test Metrics: N/A")
            
        print(f"\nExperiment ID: {exp.experiment_id}")
        print(f"\nStatus: {exp.status}")
        print("================================================")
        
        if args.output_json:
            out_data = {
                "experiment_id": exp.experiment_id,
                "name": exp.experiment_name,
                "status": exp.status,
                "classification": exp.classification
            }
            out_path = Path(args.output_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(out_data, f, indent=2)
            print(f"Result JSON saved to {out_path.resolve()}")

        return 0

    except Exception as e:
        logger.exception("Research experiment failed due to an internal error.")
        print(f"Error: {e}")
        return 1
