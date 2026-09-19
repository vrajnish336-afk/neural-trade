import sys
import argparse
from app.config import config
from app.execution.safety import ExecutionSafetyGate
from app.cli.commands.backtest import setup_backtest_parser
from app.cli.commands.research import setup_research_parser
from app.cli.commands.status import setup_status_parser

def _enforce_safety():
    """
    Enforces that the system is operating in a safe paper-trading / research mode.
    Exits with code 1 immediately if any condition fails.
    """
    if not config.PAPER_TRADING:
        print("SAFETY ERROR: PAPER_TRADING is disabled. The CLI requires PAPER_TRADING=True.", file=sys.stderr)
        sys.exit(1)
        
    if config.LIVE_TRADING:
        print("SAFETY ERROR: LIVE_TRADING is enabled. The CLI strictly forbids LIVE_TRADING.", file=sys.stderr)
        sys.exit(1)
        
    if ExecutionSafetyGate.is_live_trading_allowed():
        print("CRITICAL SAFETY ERROR: ExecutionSafetyGate allowed live trading. Aborting.", file=sys.stderr)
        sys.exit(1)

def run_cli() -> int:
    _enforce_safety()
    
    parser = argparse.ArgumentParser(
        prog="ntrade",
        description="Neural Trade Professional Research CLI"
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    setup_backtest_parser(subparsers)
    setup_research_parser(subparsers)
    setup_status_parser(subparsers)
    from app.cli.commands.analyze import setup_analyze_parser
    from app.cli.commands.compare import setup_compare_parser
    from app.cli.commands.evaluate import setup_evaluate_parser
    from app.cli.commands.news import setup_news_parser
    from app.cli.commands.research_news import setup_research_news_parser
    from app.cli.commands.research_loop import setup_research_loop_parser
    from app.cli.commands.research_memory import setup_research_memory_parser
    from app.cli.commands.research_jobs import setup_research_jobs_parser
    from app.cli.commands.research_decisions import setup_research_decision_parser
    from app.cli.commands.research_knowledge import setup_research_knowledge_parser
    from app.cli.commands.forward_validation import setup_forward_validation_parser
    from app.cli.commands.track_record import setup_paper_track_parser
    from app.cli.commands.monitor import setup_paper_monitor_parser
    from app.cli.commands.portfolio import setup_portfolio_parser
    from app.cli.commands.learning import setup_learning_parser
    from app.cli.commands.forecasting import setup_forecasting_parser
    from app.cli.commands.intelligence import setup_intelligence_parser
    from app.cli.commands.copilot import setup_copilot_parser
    from app.cli.commands.sandbox import setup_sandbox_parser
    from app.cli.commands.experiment import setup_experiment_parser
    from app.cli.commands.evolution import setup_evolution_parser
    from app.cli.commands.continuous import setup_continuous_parser
    from app.cli.commands.evidence_graph import setup_evidence_graph_parser
    from app.cli.commands.planner import setup_planner_parser
    from app.cli.commands.synthesis import setup_synthesis_parser
    from app.cli.commands.hypothesis_validation import setup_validation_parser
    from app.cli.commands.replication import setup_replication_parser
    from app.cli.commands.revalidation import setup_revalidation_parser
    from app.cli.commands.consensus import setup_consensus_parser
    from app.cli.commands.causality import setup_causality_parser
    from app.cli.commands.causal_experiments import setup_causal_experiment_parser
    from app.cli.commands.temporal_generalization import setup_temporal_parser
    from app.cli.commands.multi_timeframe import setup_multi_timeframe_parser
    from app.cli.commands.portfolio_intelligence import setup_portfolio_intelligence_parser
    from app.cli.commands.portfolio_stress import setup_portfolio_stress_parser
    from app.cli.commands.portfolio_discovery import setup_portfolio_discovery_parser
    from app.cli.commands.meta_analysis import setup_meta_analysis_parser
    from app.cli.commands.governance import setup_governance_parser
    from app.cli.commands.reproduction import setup_reproduction_parser
    from app.cli.commands.discrepancy_intelligence import setup_discrepancy_intelligence_parser
    from app.cli.commands.discrepancy_isolation import setup_discrepancy_isolation_parser
    from app.cli.commands.revalidation_cli import setup_revalidation_parser as setup_revalidation_cli_parser
    from app.cli.commands.knowledge_intelligence_cli import setup_knowledge_intelligence_parser
    from app.cli.commands.knowledge_graph_cli import setup_knowledge_graph_parser
    from app.cli.commands.reasoning_cli import setup_reasoning_parser
    from app.cli.commands.lineage_cli import setup_lineage_parser
    
    setup_analyze_parser(subparsers)
    setup_compare_parser(subparsers)
    setup_evaluate_parser(subparsers)
    setup_news_parser(subparsers)
    setup_research_news_parser(subparsers)
    setup_research_loop_parser(subparsers)
    setup_research_memory_parser(subparsers)
    setup_research_jobs_parser(subparsers)
    setup_research_decision_parser(subparsers)
    setup_research_knowledge_parser(subparsers)
    setup_forward_validation_parser(subparsers)
    setup_paper_track_parser(subparsers)
    setup_paper_monitor_parser(subparsers)
    setup_portfolio_parser(subparsers)
    setup_learning_parser(subparsers)
    setup_forecasting_parser(subparsers)
    setup_intelligence_parser(subparsers)
    setup_copilot_parser(subparsers)
    setup_sandbox_parser(subparsers)
    setup_experiment_parser(subparsers)
    setup_evolution_parser(subparsers)
    setup_continuous_parser(subparsers)
    setup_evidence_graph_parser(subparsers)
    setup_planner_parser(subparsers)
    setup_synthesis_parser(subparsers)
    setup_validation_parser(subparsers)
    setup_replication_parser(subparsers)
    setup_revalidation_parser(subparsers)
    setup_consensus_parser(subparsers)
    setup_causality_parser(subparsers)
    setup_causal_experiment_parser(subparsers)
    setup_temporal_parser(subparsers)
    setup_multi_timeframe_parser(subparsers)
    setup_portfolio_intelligence_parser(subparsers)
    setup_portfolio_stress_parser(subparsers)
    setup_portfolio_discovery_parser(subparsers)
    setup_meta_analysis_parser(subparsers)
    setup_governance_parser(subparsers)
    setup_reproduction_parser(subparsers)
    setup_discrepancy_intelligence_parser(subparsers)
    setup_discrepancy_isolation_parser(subparsers)
    setup_revalidation_cli_parser(subparsers)
    setup_knowledge_intelligence_parser(subparsers)
    setup_knowledge_graph_parser(subparsers)
    setup_reasoning_parser(subparsers)
    setup_lineage_parser(subparsers)
    
    args = parser.parse_args()
    
    if hasattr(args, "func"):
        return args.func(args)
    
    return 0
