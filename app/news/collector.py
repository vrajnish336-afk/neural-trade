import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import logging
from typing import List
from app.config import config
from app.news.normalizer import normalize_rss_item
from app.news.models import IngestedNewsRecord

logger = logging.getLogger(__name__)

class NewsCollector:
    def __init__(self, feeds: List[str] = None, timeout: int = None, max_size: int = None):
        self.feeds = feeds if feeds is not None else config.NEWS_FEEDS
        self.timeout = timeout if timeout is not None else config.NEWS_FETCH_TIMEOUT
        self.max_size = max_size if max_size is not None else config.NEWS_MAX_RESPONSE_SIZE
        
    def collect(self) -> List[IngestedNewsRecord]:
        records = []
        for feed_url in self.feeds:
            if not feed_url.strip():
                continue
            feed_records = self._fetch_and_parse_feed(feed_url)
            records.extend(feed_records)
        return records

    def _fetch_and_parse_feed(self, feed_url: str) -> List[IngestedNewsRecord]:
        logger.info(f"Fetching RSS feed: {feed_url}")
        req = urllib.request.Request(
            feed_url, 
            headers={'User-Agent': 'NeuralTrade/1.0'}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content = response.read(self.max_size + 1)
                if len(content) > self.max_size:
                    logger.warning(f"Feed {feed_url} exceeded max size of {self.max_size} bytes. Skipping.")
                    return []
                    
                root = ET.fromstring(content)
                return self._parse_rss_root(root, feed_url)
                
        except urllib.error.URLError as e:
            logger.warning(f"Network error fetching {feed_url}: {e}")
        except ET.ParseError as e:
            logger.warning(f"XML parse error for {feed_url}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error fetching {feed_url}: {e}")
            
        return []

    def _parse_rss_root(self, root: ET.Element, feed_url: str) -> List[IngestedNewsRecord]:
        records = []
        # Support for standard RSS 2.0
        channel = root.find('channel')
        if channel is None:
            logger.warning(f"No <channel> found in RSS feed: {feed_url}")
            return records
            
        source_title_elem = channel.find('title')
        source_title = source_title_elem.text if source_title_elem is not None else 'Unknown Source'
        
        for item in channel.findall('item'):
            try:
                item_dict = {}
                for child in item:
                    # Strip namespace if present
                    tag = child.tag.split('}', 1)[-1]
                    item_dict[tag] = child.text
                    
                record = normalize_rss_item(item_dict, feed_url, source_title)
                records.append(record)
            except Exception as e:
                logger.debug(f"Failed to normalize an item in {feed_url}: {e}")
                
        return records
