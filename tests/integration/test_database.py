import pytest
import os
import sqlite3
from app.database.connection import DatabaseConnection

@pytest.fixture
def temp_db_url(tmp_path):
    """Provides a temporary database URL for tests."""
    db_file = tmp_path / "test_bot.db"
    return f"sqlite:///{db_file}"

def test_database_initialization(temp_db_url):
    """Test that the database initializes correctly in a new location."""
    db = DatabaseConnection(db_url=temp_db_url)
    
    # Path should not exist yet (or might, depending on pytest tempdir)
    # Let's initialize
    db.initialize()
    
    # Verify file was created
    db_path = temp_db_url.replace("sqlite:///", "")
    assert os.path.exists(db_path)
    
    # Verify we can get a connection
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

def test_get_connection_row_factory(temp_db_url):
    """Test that connection returns rows as dict-like objects."""
    db = DatabaseConnection(db_url=temp_db_url)
    db.initialize()
    
    with db.get_connection() as conn:
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test_table (name) VALUES ('test_name')")
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM test_table")
        row = cursor.fetchone()
        
        # Verify sqlite3.Row dict-like access
        assert row["name"] == "test_name"
        assert row["id"] == 1
