"""
Portugal Data Intelligence - ETL: Load Module
===============================================
Loads processed DataFrames into the SQLite database, creating the
schema and seeding dimension tables as needed.

Each fact table has a dedicated load function that maps DataFrame
columns to database columns and performs INSERT OR REPLACE operations.

Usage:
    from src.etl.load import load_all
    load_all(processed_data)
"""

import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple

import pandas as pd

from config.settings import (
    DATA_PILLARS,
    DATA_SOURCES,
    DATABASE_DIR,
    DATABASE_PATH,
    DDL_DIR,
    SQLITE_PRAGMAS,
)
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)

# Whitelist of safe PRAGMA names that may be applied to the database.
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


# ============================================================================
# DATABASE CONNECTION HELPERS
# ============================================================================


def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the SQLite database and apply PRAGMA settings.

    Creates the database directory if it does not exist.

    Returns
    -------
    sqlite3.Connection
        An open SQLite connection with configured pragmas.
    """
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()

    # Apply PRAGMA settings from config (validated against whitelist)
    for pragma, value in SQLITE_PRAGMAS.items():
        if pragma not in _SAFE_PRAGMAS:
            logger.warning(f"  Skipping unknown PRAGMA '{pragma}' — " f"not in whitelist")
            continue
        stmt = f"PRAGMA {pragma} = {value};"
        cursor.execute(stmt)
        logger.debug(f"  Applied {stmt.strip()}")

    conn.commit()
    logger.info(f"Connected to database: {DATABASE_PATH}")
    return conn


def close_connection(conn: sqlite3.Connection) -> None:
    """
    Safely close a database connection.

    Parameters
    ----------
    conn : sqlite3.Connection
        The connection to close.
    """
    try:
        conn.close()
        logger.info("Database connection closed")
    except Exception as exc:
        logger.error(f"Error closing database connection: {exc}")


@contextmanager
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that opens and automatically closes a DB connection.

    Usage::

        with db_connection() as conn:
            conn.execute("SELECT ...")
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        close_connection(conn)


# ============================================================================
# DATABASE INITIALISATION
# ============================================================================


def initialise_database(conn: sqlite3.Connection) -> None:
    """
    Run DDL and seed scripts to set up the database schema.

    Executes create_tables.sql followed by seed_dimensions.sql from
    the sql/ddl/ directory.  If the scripts have already been run the
    DROP IF EXISTS / INSERT statements ensure idempotency.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection.
    """
    logger.info("Initialising database schema...")

    ddl_scripts = [
        DDL_DIR / "create_tables.sql",
        DDL_DIR / "seed_dimensions.sql",
        DDL_DIR / "create_benchmark_tables.sql",
    ]

    cursor = conn.cursor()

    for script_path in ddl_scripts:
        if not script_path.exists():
            logger.error(f"DDL script not found: {script_path}")
            continue

        logger.info(f"  Executing: {script_path.name}")
        try:
            sql = script_path.read_text(encoding="utf-8")
            cursor.executescript(sql)
            logger.info(f"  Completed: {script_path.name}")
        except sqlite3.Error as exc:
            logger.error(f"  Failed to execute {script_path.name}: {exc}")
            raise

    conn.commit()
    _source_key_cache.clear()
    logger.info("Database schema initialised successfully")


# ============================================================================
# SOURCE KEY LOOKUP
# ============================================================================

# Cache for source_key lookups (avoids repeated queries per row batch).
_source_key_cache: Dict[str, Optional[int]] = {}


def _get_source_key(conn: sqlite3.Connection, source_name: str) -> Optional[int]:
    """Look up the source_key for a given data source name (cached)."""
    if source_name in _source_key_cache:
        return _source_key_cache[source_name]

    cursor = conn.cursor()
    cursor.execute(
        "SELECT source_key FROM dim_source WHERE source_name = ?",
        (source_name,),
    )
    row = cursor.fetchone()
    key = row[0] if row else None
    _source_key_cache[source_name] = key
    return key


def _resolve_source_key(conn: sqlite3.Connection, pillar_key: str) -> Optional[int]:
    """
    Determine the appropriate source_key for a pillar.

    Uses the first entry in the pillar's primary_sources list from
    DATA_PILLARS config.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection.
    pillar_key : str
        The pillar identifier (e.g. 'gdp').

    Returns
    -------
    int or None
        The source_key for the pillar's primary source.
    """
    pillar_config = DATA_PILLARS.get(pillar_key, {})
    sources = pillar_config.get("primary_sources", [])

    if not sources:
        logger.warning(f"No primary sources defined for pillar '{pillar_key}'")
        return None

    # Use the first listed source
    source_key = _get_source_key(conn, sources[0])
    if source_key is None:
        logger.warning(f"Source '{sources[0]}' not found in dim_source for pillar '{pillar_key}'")
    return source_key


# ============================================================================
# VALUE CONVERSION HELPER
# ============================================================================


def _to_float(value) -> Optional[float]:
    """
    Safely convert a value to float, returning None for NaN / missing.

    Parameters
    ----------
    value
        Any scalar value from a DataFrame cell.

    Returns
    -------
    float or None
    """
    if value is None:
        return None
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


# ============================================================================
# GENERIC PILLAR LOAD
# ============================================================================


def _insert_or_replace(
    conn: sqlite3.Connection,
    table_name: str,
    columns: List[str],
    rows: List[Tuple],
    pillar_key: str,
) -> int:
    """
    Perform INSERT OR REPLACE for a batch of rows.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection.
    table_name : str
        The target table name.
    columns : list[str]
        Column names matching the row tuples.
    rows : list[tuple]
        Data rows to insert.
    pillar_key : str
        The pillar key for log messages.

    Returns
    -------
    int
        Number of rows inserted.
    """
    if not rows:
        logger.warning(f"  [{pillar_key}] No rows to load into {table_name}")
        return 0

    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    sql = f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})"

    cursor = conn.cursor()
    cursor.executemany(sql, rows)
    conn.commit()

    loaded = len(rows)
    logger.info(f"  [{pillar_key}] Loaded {loaded:,} rows into {table_name}")
    return loaded


def _load_pillar(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    *,
    pillar_key: str,
    table_name: str,
    value_columns: List[str],
) -> int:
    """
    Generic loader for any pillar fact table.

    Every fact table follows the same pattern: resolve the source key,
    iterate rows extracting ``date_key`` (as string) plus the listed
    value columns (converted via ``_to_float``), then bulk-insert.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open database connection.
    df : pd.DataFrame
        Processed DataFrame for the pillar.
    pillar_key : str
        The pillar identifier (e.g. 'gdp').
    table_name : str
        The target fact table (e.g. 'fact_gdp').
    value_columns : list[str]
        Column names for the numeric values (excluding ``date_key``
        and ``source_key`` which are handled automatically).

    Returns
    -------
    int
        Number of rows loaded.
    """
    source_key = _resolve_source_key(conn, pillar_key)
    if source_key is None:
        raise ValueError(
            f"[{pillar_key}] Cannot resolve source_key — "
            f"check dim_source is seeded and DATA_PILLARS.primary_sources is correct"
        )

    # Include is_provisional if present in the DataFrame
    has_provisional = "is_provisional" in df.columns
    all_value_cols = value_columns + (["is_provisional"] if has_provisional else [])

    # Validate that required columns exist in the DataFrame
    missing = [c for c in ["date_key"] + value_columns if c not in df.columns]
    if missing:
        raise ValueError(f"[{pillar_key}] Missing required columns: {', '.join(missing)}")

    columns = ["date_key"] + all_value_cols + ["source_key"]

    rows = []
    for values in df.itertuples(index=False):
        provisional_val = ()
        if has_provisional:
            provisional_val = (int(bool(getattr(values, "is_provisional", False))),)
        row = (
            str(getattr(values, "date_key", "")),
            *(_to_float(getattr(values, col, None)) for col in value_columns),
            *provisional_val,
            source_key,
        )
        rows.append(row)

    return _insert_or_replace(conn, table_name, columns, rows, pillar_key)


# ============================================================================
# PILLAR CONFIGURATIONS
# ============================================================================

_PILLAR_CONFIGS: Dict[str, dict] = {
    "gdp": {
        "table_name": "fact_gdp",
        "value_columns": [
            "nominal_gdp",
            "real_gdp",
            "gdp_growth_yoy",
            "gdp_growth_qoq",
            "gdp_per_capita",
        ],
    },
    "unemployment": {
        "table_name": "fact_unemployment",
        "value_columns": [
            "unemployment_rate",
            "youth_unemployment_rate",
            "long_term_unemployment_rate",
            "labour_force_participation_rate",
        ],
    },
    "credit": {
        "table_name": "fact_credit",
        "value_columns": [
            "total_credit",
            "credit_nfc",
            "credit_households",
            "npl_ratio",
        ],
    },
    "interest_rates": {
        "table_name": "fact_interest_rates",
        "value_columns": [
            "ecb_main_refinancing_rate",
            "euribor_3m",
            "euribor_6m",
            "euribor_12m",
            "portugal_10y_bond_yield",
        ],
    },
    "inflation": {
        "table_name": "fact_inflation",
        "value_columns": [
            "hicp",
            "cpi_estimated",
            "core_inflation",
        ],
    },
    "public_debt": {
        "table_name": "fact_public_debt",
        "value_columns": [
            "total_debt",
            "debt_to_gdp_ratio",
            "budget_deficit",
            "budget_deficit_annual",
            "external_debt_share_estimated",
        ],
    },
}


# ============================================================================
# PILLAR-SPECIFIC THIN WRAPPERS
# ============================================================================


def load_gdp(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Load processed GDP data into fact_gdp."""
    return _load_pillar(conn, df, pillar_key="gdp", **_PILLAR_CONFIGS["gdp"])


def load_unemployment(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Load processed unemployment data into fact_unemployment."""
    return _load_pillar(conn, df, pillar_key="unemployment", **_PILLAR_CONFIGS["unemployment"])


def load_credit(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Load processed credit data into fact_credit."""
    return _load_pillar(conn, df, pillar_key="credit", **_PILLAR_CONFIGS["credit"])


def load_interest_rates(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Load processed interest rates data into fact_interest_rates."""
    return _load_pillar(conn, df, pillar_key="interest_rates", **_PILLAR_CONFIGS["interest_rates"])


def load_inflation(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Load processed inflation data into fact_inflation."""
    return _load_pillar(conn, df, pillar_key="inflation", **_PILLAR_CONFIGS["inflation"])


def load_public_debt(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Load processed public debt data into fact_public_debt."""
    return _load_pillar(conn, df, pillar_key="public_debt", **_PILLAR_CONFIGS["public_debt"])


# ============================================================================
# LOAD ALL
# ============================================================================

# Dispatch table mapping pillar keys to their load functions.
_LOAD_DISPATCH: Dict[str, Callable] = {
    "gdp": load_gdp,
    "unemployment": load_unemployment,
    "credit": load_credit,
    "interest_rates": load_interest_rates,
    "inflation": load_inflation,
    "public_debt": load_public_debt,
}


def load_all(
    processed_data: Dict[str, pd.DataFrame],
    initialise: bool = True,
) -> Dict[str, int]:
    """
    Load all processed DataFrames into the database.

    Parameters
    ----------
    processed_data : dict[str, pd.DataFrame]
        Dictionary of processed DataFrames keyed by pillar name.
    initialise : bool
        If True, run DDL and seed scripts before loading.  Defaults
        to True so the database is always in a known state.

    Returns
    -------
    dict[str, int]
        Dictionary mapping pillar names to the number of rows loaded.
    """
    log_section(logger, "LOAD PHASE")

    row_counts: Dict[str, int] = {}

    with db_connection() as conn:
        # Initialise schema and seed dimension tables
        if initialise:
            initialise_database(conn)

        # Load each pillar
        for pillar_key, df in processed_data.items():
            load_fn = _LOAD_DISPATCH.get(pillar_key)
            if load_fn is None:
                logger.warning(f"No load function for pillar '{pillar_key}' - skipping")
                continue

            try:
                count = load_fn(conn, df)
                row_counts[pillar_key] = count
            except Exception as exc:
                logger.error(f"Load failed for '{pillar_key}': {exc}")
                row_counts[pillar_key] = 0

        # Summary
        total_rows = sum(row_counts.values())
        logger.info(
            f"Load complete: {total_rows:,} total rows across " f"{len(row_counts)} pillar(s)"
        )

    return row_counts
