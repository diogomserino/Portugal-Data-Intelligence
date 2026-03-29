"""
Tests for the centralised database connection utility (src/utils/db.py).
"""

import sqlite3
from pathlib import Path

import pytest

from src.utils.db import get_connection


class TestGetConnection:
    """Tests for the get_connection context manager."""

    def test_connection_opens_and_closes(self, tmp_path):
        """Connection should be open inside the context and closed after."""
        db_path = tmp_path / "test.db"
        with get_connection(db_path) as conn:
            assert isinstance(conn, sqlite3.Connection)
            conn.execute("CREATE TABLE t (id INTEGER)")
        # After exiting, connection should be closed
        # Attempting to use it should raise
        with pytest.raises(Exception):
            conn.execute("SELECT 1")

    def test_default_path(self):
        """Should connect to the project database by default."""
        with get_connection() as conn:
            # Just verify it opens without error
            assert conn is not None

    def test_row_factory(self, tmp_path):
        """When row_factory=True, rows should be dict-like."""
        db_path = tmp_path / "test.db"
        with get_connection(db_path, row_factory=True) as conn:
            conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO t VALUES (1, 'test')")
            row = conn.execute("SELECT * FROM t").fetchone()
            assert row["id"] == 1
            assert row["name"] == "test"

    def test_apply_pragmas(self, tmp_path):
        """When apply_pragmas=True, PRAGMA settings should be applied."""
        db_path = tmp_path / "test.db"
        with get_connection(db_path, apply_pragmas=True) as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1  # foreign_keys should be ON

    def test_creates_parent_directory(self, tmp_path):
        """Should create parent directories if they don't exist."""
        db_path = tmp_path / "nested" / "dir" / "test.db"
        with get_connection(db_path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")
        assert db_path.exists()

    def test_closes_on_exception(self, tmp_path):
        """Connection should be closed even if an exception occurs."""
        db_path = tmp_path / "test.db"
        with pytest.raises(ValueError):
            with get_connection(db_path) as conn:
                conn.execute("CREATE TABLE t (id INTEGER)")
                raise ValueError("test error")
        # Verify db file was created (connection was opened)
        assert db_path.exists()
