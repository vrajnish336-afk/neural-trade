import sys, os
sys.path.append(os.getcwd())
import time, logging
from app.config import config
config.NEWS_CREDIBILITY_FILTER_ENABLED = True
from app.intelligence.adapters.news import NewsAdapter
logging.basicConfig(level=logging.INFO)
adapter = NewsAdapter()
start = time.time()
records = adapter.collector.collect()[:2]
adapter.collector.collect = lambda: records
obs = adapter.fetch_observations()
latency = time.time() - start
print(f'LATENCY: {latency}')
print(f'OBS_COUNT: {len(obs)}')

