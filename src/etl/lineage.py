"""
Portugal Data Intelligence - Pipeline Lineage & Batch Tracking
================================================================
Tracks each pipeline run with a unique correlation ID, records
row counts, checksums, and timings for every pillar at each stage.

Usage:
    from src.etl.lineage import PipelineTracker
    with PipelineTracker(mode="full") as tracker:
        tracker.record("gdp", "extract", rows_in=0, rows_out=64)
"""

import hashlib
import sqlite3
import time
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import DATABASE_PATH, DDL_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Context variable for correlation — accessible from any module via get_run_id().
_run_id_var: ContextVar[Optional[str]] = ContextVar("run_id", default=None)

PIPELINE_VERSION = "2.0.0"


def get_run_id() -> Optional[str]:
    """Return the current pipeline run ID, or None outside a tracked run."""
    return _run_id_var.get()


def file_checksum(path: Path, algorithm: str = "sha256") -> Optional[str]:
    """Compute hex digest of a file; return None on error."""
    try:
        h = hashlib.new(algorithm)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, ValueError):
        return None


@dataclass
class LineageRecord:
    """Single lineage entry for one pillar at one pipeline stage."""

    run_id: str
    pillar: str
    stage: str  # extract | transform | load
    rows_in: int = 0
    rows_out: int = 0
    null_count: int = 0
    checksum: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PipelineTracker:
    """Context manager that tracks a full pipeline run.

    Generates a UUID-based ``run_id`` and stores run metadata plus
    per-pillar lineage records in the ``pipeline_runs`` and
    ``data_lineage`` tables.

    Parameters
    ----------
    mode : str
        Pipeline mode (e.g. ``'full'``, ``'etl'``, ``'analysis'``).
    db_path : Path, optional
        Override the default database path (useful for testing).
    """

    DDL_FILE = "create_lineage_tables.sql"

    def __init__(self, mode: str = "full", db_path: Optional[Path] = None):
        self.run_id: str = uuid.uuid4().hex[:16]
        self.mode: str = mode
        self.db_path: Path = db_path or DATABASE_PATH
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.records: List[LineageRecord] = []
        self._start_time: float = time.time()
        self._token: Optional[Token[Optional[str]]] = None

    # -- context manager -------------------------------------------------------

    def __enter__(self) -> "PipelineTracker":
        self._token = _run_id_var.set(self.run_id)
        logger.info("Pipeline run started  [run_id=%s  mode=%s]", self.run_id, self.mode)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration = time.time() - self._start_time
        status = "failed" if exc_type else "completed"
        self._persist(status, duration)
        assert self._token is not None, "PipelineTracker.__exit__ called without __enter__"
        _run_id_var.reset(self._token)
        logger.info(
            "Pipeline run %s  [run_id=%s  duration=%.2fs  records=%d]",
            status,
            self.run_id,
            duration,
            len(self.records),
        )
        return None  # do not suppress exceptions

    # -- public API ------------------------------------------------------------

    def record(
        self,
        pillar: str,
        stage: str,
        rows_in: int = 0,
        rows_out: int = 0,
        null_count: int = 0,
        checksum: Optional[str] = None,
    ) -> None:
        """Append a lineage record for *pillar* at *stage*."""
        rec = LineageRecord(
            run_id=self.run_id,
            pillar=pillar,
            stage=stage,
            rows_in=rows_in,
            rows_out=rows_out,
            null_count=null_count,
            checksum=checksum,
        )
        self.records.append(rec)
        logger.debug(
            "Lineage: %s/%s  in=%d out=%d nulls=%d",
            pillar,
            stage,
            rows_in,
            rows_out,
            null_count,
        )

    # -- persistence -----------------------------------------------------------

    def _ensure_tables(self, conn: sqlite3.Connection) -> None:
        """Create lineage tables if they do not exist."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id          TEXT PRIMARY KEY,
                started_at      TEXT NOT NULL,
                completed_at    TEXT NOT NULL,
                status          TEXT NOT NULL CHECK(status IN ('completed','failed')),
                mode            TEXT NOT NULL,
                version         TEXT NOT NULL,
                duration_seconds REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS data_lineage (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      TEXT NOT NULL,
                pillar      TEXT NOT NULL,
                stage       TEXT NOT NULL CHECK(stage IN ('extract','transform','load')),
                rows_in     INTEGER NOT NULL DEFAULT 0,
                rows_out    INTEGER NOT NULL DEFAULT 0,
                null_count  INTEGER NOT NULL DEFAULT 0,
                checksum    TEXT,
                timestamp   TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs (run_id)
            );
            """)

    def _persist(self, status: str, duration: float) -> None:
        """Write run metadata and lineage records to the database."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            try:
                self._ensure_tables(conn)

                completed_at = datetime.now(timezone.utc).isoformat()

                conn.execute(
                    "INSERT OR REPLACE INTO pipeline_runs "
                    "(run_id, started_at, completed_at, status, mode, version, duration_seconds) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.run_id,
                        self.started_at,
                        completed_at,
                        status,
                        self.mode,
                        PIPELINE_VERSION,
                        duration,
                    ),
                )

                conn.executemany(
                    "INSERT INTO data_lineage "
                    "(run_id, pillar, stage, rows_in, rows_out, null_count, checksum, timestamp) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            r.run_id,
                            r.pillar,
                            r.stage,
                            r.rows_in,
                            r.rows_out,
                            r.null_count,
                            r.checksum,
                            r.timestamp,
                        )
                        for r in self.records
                    ],
                )

                conn.commit()
                logger.info(
                    "Lineage persisted: %d records for run %s", len(self.records), self.run_id
                )
            finally:
                conn.close()
        except Exception as exc:
            logger.error("Failed to persist lineage data: %s", exc)
