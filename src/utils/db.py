"""
Portugal Data Intelligence — Database Connection Utility
==========================================================
Centralised database connection management for all project modules.

Provides a context manager that ensures connections are always closed,
even when exceptions occur.

Usage:
    from src.utils.db import get_connection

    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM fact_gdp", conn)
    # Connection is automatically closed here

    # Or with a custom database path:
    with get_connection(db_path="path/to/db.sqlite") as conn:
        ...
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union

from config.settings import DATABASE_DIR, DATABASE_PATH, SQLITE_PRAGMAS
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Whitelist of safe PRAGMA names
_SAFE_PRAGMAS = frozenset(
    {
        "journal_mode",
        "synchronous",
        "cache_size",
        "foreign_keys",
        "temp_store",
        "mmap_size",
        "page_size",
        "wal_autocheckpoint",
        "busy_timeout",
        "locking_mode",
        "auto_vacuum",
        "encoding",
    }
)


@contextmanager
def get_connection(
    db_path: Optional[Union[str, Path]] = None,
    apply_pragmas: bool = False,
    row_factory: bool = False,
):
    """Context manager for SQLite database connections.

    Ensures the connection is always closed, even if an exception occurs.

    Parameters
    ----------
    db_path : str or Path, optional
        Path to the SQLite database. Defaults to the project database.
    apply_pragmas : bool
        If True, apply performance PRAGMAs from config (for write operations).
    row_factory : bool
        If True, set ``sqlite3.Row`` as the row factory for dict-like access.

    Yields
    ------
    sqlite3.Connection
        An open SQLite connection.

    Examples
    --------
    >>> with get_connection() as conn:
    ...     df = pd.read_sql("SELECT * FROM fact_gdp", conn)
    """
    path = str(db_path or DATABASE_PATH)

    # Ensure directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)

    try:
        if row_factory:
            conn.row_factory = sqlite3.Row

        if apply_pragmas:
            for pragma, value in SQLITE_PRAGMAS.items():
                if pragma in _SAFE_PRAGMAS:
                    conn.execute(f"PRAGMA {pragma} = {value};")

        yield conn
    finally:
        conn.close()
