import sys, os, time, logging, sqlite3
sys.path.append(os.getcwd())
import ccxt
import urllib3
urllib3.disable_warnings()
from datetime import datetime, timezone, timedelta
from app.config import config
config.PAPER_TRADING = True
config.LIVE_TRADING = False
config.KRONOS_ENABLED = True
from app.database.schema import SCHEMA_SQL
with sqlite3.connect('data/paper_trading.db') as conn:
    conn.executescript(SCHEMA_SQL)
from app.broker.adapters import ReadOnlyLiveMarketDataAdapter
from app.intelligence.service import WorldIntelligenceService
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.breakout import BreakoutStrategy
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.execution.paper_repository import PaperRepository
from app.forecasting.service import ForecastingService
from app.risk.drawdown import DrawdownService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ccxt_exchange = ccxt.binance({
    'options': {'fetchMarkets': {'types': ['spot']}},
    'urls': {
        'api': {
            'public': 'https://data-api.binance.vision/api/v3',
            'v1': 'https://data-api.binance.vision/api/v1',
            'v3': 'https://data-api.binance.vision/api/v3'
        }
    }
})
ccxt_exchange.session = __import__('requests').Session()
ccxt_exchange.session.verify = False
provider = ReadOnlyLiveMarketDataAdapter(provider=ccxt_exchange)
symbols = ['BTC/USDT', 'ETH/USDT']
tf = '1h'
paper_repo = PaperRepository(db_path='data/paper_trading.db')
pid = 'test_paper_run'
paper_repo.get_or_create_portfolio(pid, initial_equity=10000.0)

fs = ForecastingService(data_dir='data/historical')
risk_limits = PortfolioRiskLimits(initial_equity=10000.0)
risk_engine = RiskEngine(risk_limits, risk_per_trade_pct=0.02)
ensemble = StrategyEnsemble([BreakoutStrategy(), TrendFollowingStrategy(), MeanReversionStrategy()], min_score=0.0)
from app.services.intelligence import IntelligenceService
from app.news.provider import FixtureNewsProvider
intel_old = IntelligenceService(FixtureNewsProvider(), config)
intel = WorldIntelligenceService()
intel.fetch_and_store_all()
broker = StreamingPaperBroker(repository=paper_repo, risk_engine=risk_engine, portfolio_id=pid)
orch = DecisionOrchestrator(ensemble=ensemble, risk_engine=risk_engine, intelligence_service=intel_old, world_intelligence_service=intel, forecasting_service=fs, paper_repository=paper_repo, drawdown_service=DrawdownService(), data_provider=provider)

for sym in symbols:
    logger.info(f'Fetching {sym}')
    start_time = datetime.now(timezone.utc) - timedelta(days=10)
    bars = provider.get_historical_bars(sym, tf, start_time)
    
    # Ensure ONLY closed candles
    now = datetime.now(timezone.utc)
    closed_bars = []
    for b in bars:
        # A 1H candle is fully closed if current time >= its timestamp + 1 hour
        if now >= b.timestamp + timedelta(hours=1):
            closed_bars.append(b)
            
    logger.info(f'Fetched {len(bars)} bars. Closed bars: {len(closed_bars)}. Latest closed: {closed_bars[-1].timestamp if closed_bars else "None"}')
    
    if len(closed_bars) > 100:
        curr_portfolio = dict(paper_repo.get_or_create_portfolio(pid))
        d = orch.evaluate(sym, closed_bars, curr_portfolio['current_equity'], 0, 0, pid)
        logger.info(f'Raw strategy signals for {sym}: {d.strategy_signals}')
        logger.info(f'Decision: {d.decision} Veto: {d.risk_gate_reason}')
        if d.decision != "NO_TRADE":
            res = broker.execute_decision(d, position_size=0.1)
            logger.info(f'Execution result: {res}')

# Print portfolio at end
p = dict(paper_repo.get_or_create_portfolio(pid))
logger.info(f'Final Portfolio Equity: {p["current_equity"]}')
