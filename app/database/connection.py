import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Generator
from app.config import config

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Manages SQLite database connections and initialization."""
    
    def __init__(self, db_url: str = None):
        # We expect a format like sqlite:///data/trading_bot.db
        raw_url = db_url or config.DATABASE_URL
        if raw_url.startswith("sqlite:///"):
            self.db_path = raw_url.replace("sqlite:///", "")
        else:
            self.db_path = raw_url
            
    def initialize(self) -> None:
        """Create the database directory if needed and ensure the db file can be created."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info("Created database directory at: %s", db_dir)
            
        # Try connecting to ensure initialization is successful
        try:
            with self.get_connection() as conn:
                # We can place table creation logic here in the future
                conn.execute("SELECT 1")
            logger.info("Database successfully initialized at %s", self.db_path)
        except Exception as e:
            logger.error("Failed to initialize database at %s: %s", self.db_path, e)
            raise
            
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager to yield a safe SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

# Provide a default instance
db = DatabaseConnection()
