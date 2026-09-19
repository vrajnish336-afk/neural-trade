import sqlite3
import os
import logging
from app.config import config

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS backtests (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    initial_capital REAL,
    final_equity REAL,
    total_return_pct REAL,
    number_of_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    backtest_id TEXT,
    symbol TEXT,
    direction TEXT,
    entry_time TEXT,
    exit_time TEXT,
    entry_price REAL,
    exit_price REAL,
    quantity REAL,
    realized_pnl REAL,
    exit_reason TEXT,
    regime TEXT,
    score REAL,
    strategies TEXT,
    risk_reason TEXT,
    sentiment_label TEXT,
    anomaly_flags TEXT,
    fakeout_risk TEXT,
    FOREIGN KEY(backtest_id) REFERENCES backtests(id)
);

CREATE TABLE IF NOT EXISTS equity_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id TEXT,
    timestamp TEXT,
    equity REAL,
    cash REAL,
    exposure REAL,
    drawdown REAL,
    FOREIGN KEY(backtest_id) REFERENCES backtests(id)
);

CREATE TABLE IF NOT EXISTS analytics_runs (
    id TEXT PRIMARY KEY,
    backtest_id TEXT,
    timestamp TEXT,
    report_json TEXT,
    FOREIGN KEY(backtest_id) REFERENCES backtests(id)
);

CREATE TABLE IF NOT EXISTS research_experiments (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    experiment_json TEXT
);

CREATE TABLE IF NOT EXISTS champion_challenger (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    champion_id TEXT,
    challenger_id TEXT,
    decision TEXT,
    comparison_json TEXT
);

CREATE TABLE IF NOT EXISTS news_articles (
    id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    source TEXT,
    source_url TEXT,
    article_url TEXT,
    published_timestamp TEXT,
    discovered_timestamp TEXT,
    content_hash TEXT,
    validation_status TEXT
);
CREATE TABLE IF NOT EXISTS ai_research_analysis (
    analysis_id TEXT PRIMARY KEY,
    article_id TEXT,
    analysis_timestamp TEXT,
    provider TEXT,
    model TEXT,
    schema_version TEXT,
    relevance_score REAL,
    confidence REAL,
    evidence_type TEXT,
    summary TEXT,
    market_relevance TEXT,
    affected_symbols TEXT,
    research_hypothesis TEXT,
    limitations TEXT,
    is_fallback BOOLEAN,
    error_message TEXT,
    FOREIGN KEY(article_id) REFERENCES news_articles(id)
);

CREATE TABLE IF NOT EXISTS ai_research_requests (
    request_id TEXT PRIMARY KEY,
    analysis_id TEXT,
    article_id TEXT,
    hypothesis_text TEXT,
    affected_symbols TEXT,
    mapped_strategy TEXT,
    historical_window_days INTEGER,
    dataset_identity TEXT,
    random_seed INTEGER,
    created_at TEXT,
    status TEXT,
    experiment_id TEXT,
    evidence_conclusion TEXT,
    failure_reason TEXT,
    FOREIGN KEY(analysis_id) REFERENCES ai_research_analysis(analysis_id)
);

CREATE TABLE IF NOT EXISTS research_memory (
    identity_hash TEXT PRIMARY KEY,
    canonical_hypothesis TEXT,
    affected_symbols TEXT,
    mapped_strategy TEXT,
    first_seen_at TEXT,
    last_researched_at TEXT,
    latest_experiment_id TEXT,
    latest_conclusion TEXT
);

CREATE TABLE IF NOT EXISTS research_opportunities (
    opportunity_id TEXT PRIMARY KEY,
    source_analysis_id TEXT,
    identity_hash TEXT,
    hypothesis_text TEXT,
    affected_symbols TEXT,
    mapped_strategy TEXT,
    novelty_score REAL,
    evidence_gap_score REAL,
    data_availability_score REAL,
    duplicate_penalty REAL,
    research_priority REAL,
    status TEXT,
    reason TEXT,
    created_at TEXT,
    FOREIGN KEY(source_analysis_id) REFERENCES ai_research_analysis(analysis_id),
    FOREIGN KEY(identity_hash) REFERENCES research_memory(identity_hash)
);

CREATE TABLE IF NOT EXISTS research_jobs (
    job_id TEXT PRIMARY KEY,
    opportunity_id TEXT,
    identity_hash TEXT,
    priority REAL,
    state TEXT,
    created_at TEXT,
    claimed_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    retry_count INTEGER,
    next_retry_at TEXT,
    failure_reason TEXT,
    result_experiment_id TEXT,
    FOREIGN KEY(opportunity_id) REFERENCES research_opportunities(opportunity_id)
);

CREATE INDEX IF NOT EXISTS idx_research_jobs_state ON research_jobs(state);
CREATE INDEX IF NOT EXISTS idx_research_jobs_priority ON research_jobs(priority DESC);

CREATE TABLE IF NOT EXISTS research_conclusions (
    conclusion_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    decision_state TEXT,
    confidence_state TEXT,
    summary TEXT,
    supporting_evidence_count INTEGER,
    conflicting_evidence_count INTEGER,
    limitations TEXT,
    next_research_action TEXT,
    ai_explanation TEXT,
    provenance_experiment_ids TEXT,
    created_at TEXT,
    FOREIGN KEY(identity_hash) REFERENCES research_memory(identity_hash)
);

CREATE TABLE IF NOT EXISTS research_conflicts (
    conflict_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    experiment_id_1 TEXT,
    experiment_id_2 TEXT,
    conflict_type TEXT,
    severity TEXT,
    explanation TEXT,
    resolution_status TEXT,
    created_at TEXT,
    FOREIGN KEY(identity_hash) REFERENCES research_memory(identity_hash)
);

CREATE TABLE IF NOT EXISTS research_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    target_id TEXT,
    relationship_type TEXT,
    description TEXT
);
CREATE TABLE IF NOT EXISTS research_knowledge_changes (
    change_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    change_type TEXT,
    previous_decision TEXT,
    new_decision TEXT,
    previous_confidence TEXT,
    new_confidence TEXT,
    reason TEXT,
    source_reference_id TEXT,
    created_at TEXT,
    FOREIGN KEY(identity_hash) REFERENCES research_memory(identity_hash)
);

CREATE TABLE IF NOT EXISTS research_evidence_gaps (
    gap_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    gap_type TEXT,
    severity TEXT,
    status TEXT,
    recommended_action TEXT,
    created_at TEXT,
    resolved_at TEXT,
    FOREIGN KEY(identity_hash) REFERENCES research_memory(identity_hash)
);
CREATE TABLE IF NOT EXISTS forward_validation_runs (
    validation_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    reference_experiment_id TEXT,
    frozen_specification_json TEXT,
    dataset_identity_json TEXT,
    forward_start TEXT,
    forward_end TEXT,
    state TEXT,
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    result_experiment_id TEXT,
    failure_reason TEXT,
    drift_state TEXT,
    FOREIGN KEY(identity_hash) REFERENCES research_memory(identity_hash)
);
CREATE TABLE IF NOT EXISTS paper_track_records (
    track_record_id TEXT PRIMARY KEY,
    identity_hash TEXT,
    frozen_specification_hash TEXT,
    initial_equity REAL,
    current_equity REAL,
    cumulative_pnl REAL,
    cumulative_return_pct REAL,
    max_drawdown_pct REAL,
    observation_count INTEGER,
    current_health_state TEXT,
    first_observation_start TEXT,
    last_observation_end TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY(identity_hash) REFERENCES research_memory(identity_hash)
);

CREATE TABLE IF NOT EXISTS paper_observations (
    observation_id TEXT PRIMARY KEY,
    track_record_id TEXT,
    validation_id TEXT,
    observation_start TEXT,
    observation_end TEXT,
    starting_equity REAL,
    ending_equity REAL,
    net_pnl REAL,
    trade_count INTEGER,
    win_rate REAL,
    profit_factor REAL,
    drawdown_pct REAL,
    regime_distribution_json TEXT,
    drift_state TEXT,
    created_at TEXT,
    FOREIGN KEY(track_record_id) REFERENCES paper_track_records(track_record_id),
    FOREIGN KEY(validation_id) REFERENCES forward_validation_runs(validation_id)
);

CREATE TABLE IF NOT EXISTS paper_health_history (
    history_id TEXT PRIMARY KEY,
    track_record_id TEXT,
    previous_state TEXT,
    new_state TEXT,
    trigger_observation_id TEXT,
    reason TEXT,
    created_at TEXT,
    FOREIGN KEY(track_record_id) REFERENCES paper_track_records(track_record_id)
);

CREATE TABLE IF NOT EXISTS paper_monitoring_cycles (
    cycle_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    validations_discovered INTEGER NOT NULL,
    observations_recorded INTEGER NOT NULL,
    duplicates_skipped INTEGER NOT NULL,
    health_transitions INTEGER NOT NULL,
    opportunities_created INTEGER NOT NULL,
    knowledge_updates INTEGER NOT NULL,
    errors INTEGER NOT NULL,
    error_messages_json TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT
);

CREATE TABLE IF NOT EXISTS paper_portfolios (
    portfolio_id TEXT PRIMARY KEY,
    initial_equity REAL NOT NULL,
    current_equity REAL NOT NULL,
    current_cash REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_orders (
    order_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    decision_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    commission REAL,
    slippage REAL,
    created_at TEXT NOT NULL,
    reason TEXT,
    regime TEXT,
    strategy TEXT,
    FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
);

CREATE TABLE IF NOT EXISTS paper_positions (
    position_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    stop_loss REAL,
    take_profit REAL,
    strategy TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    regime TEXT,
    FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
);

CREATE TABLE IF NOT EXISTS paper_closed_positions (
    position_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_time TEXT NOT NULL,
    exit_price REAL NOT NULL,
    quantity REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    exit_reason TEXT,
    strategy TEXT,
    created_at TEXT NOT NULL,
    regime TEXT,
    FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
);

CREATE TABLE IF NOT EXISTS paper_equity_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    current_equity REAL NOT NULL,
    current_cash REAL NOT NULL,
    created_at TEXT NOT NULL,
    unrealized_pnl REAL DEFAULT 0.0,
    FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
);
"""

def init_db():
    if not config.ENABLE_PERSISTENCE:
        return
        
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.executescript(SCHEMA_SQL)
        
        # Add created_at to research_conflicts if it doesn't exist
        try:
            conn.execute("ALTER TABLE research_conflicts ADD COLUMN created_at TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # Add strategy to paper_positions
        try:
            conn.execute("ALTER TABLE paper_positions ADD COLUMN strategy TEXT")
        except sqlite3.OperationalError:
            pass
            
        # Add strategy to paper_closed_positions
        try:
            conn.execute("ALTER TABLE paper_closed_positions ADD COLUMN strategy TEXT")
        except sqlite3.OperationalError:
            pass

        # Add reason to paper_orders
        try:
            conn.execute("ALTER TABLE paper_orders ADD COLUMN reason TEXT")
        except sqlite3.OperationalError:
            pass

        # Add strategy to paper_orders
        try:
            conn.execute("ALTER TABLE paper_orders ADD COLUMN strategy TEXT")
            # For backward compatibility, update existing rows
            conn.execute("UPDATE paper_orders SET strategy = 'Unavailable' WHERE strategy IS NULL")
        except sqlite3.OperationalError:
            pass

        # Add unrealized_pnl to paper_equity_snapshots
        try:
            conn.execute("ALTER TABLE paper_equity_snapshots ADD COLUMN unrealized_pnl REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass

        # Add regime to paper tables
        for table in ['paper_positions', 'paper_closed_positions', 'paper_orders']:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN regime TEXT")
            except sqlite3.OperationalError:
                pass
            
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error("Failed to initialize database: %s", e)
        raise
