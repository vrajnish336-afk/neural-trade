import sys
import logging
from app.strategies.breakout import BreakoutStrategy
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy

def get_strategy_class(strategy_name: str):
    mapping = {
        "breakout": BreakoutStrategy,
        "trend_following": TrendFollowingStrategy,
        "mean_reversion": MeanReversionStrategy
    }
    strat_cls = mapping.get(strategy_name.lower())
    if not strat_cls:
        print(f"Error: Unknown strategy '{strategy_name}'")
        sys.exit(2)
    return strat_cls

def setup_cli_logging(quiet: bool):
    level = logging.ERROR if quiet else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
