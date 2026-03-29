"""
Portugal Data Intelligence - Logging Utility
==============================================
Provides a centralised, pre-configured logger for all project modules.
Supports both human-readable and structured JSON output formats.

Usage:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Pipeline started")
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

# Import settings — use fallback defaults for standalone usage.
try:
    from config.settings import LOG_DATE_FORMAT, LOG_DIR, LOG_FILE, LOG_FORMAT, LOG_LEVEL
except ImportError:
    LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
    LOG_FILE = LOG_DIR / "portugal_data_intelligence.log"
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Opt-in structured JSON logging via env var or settings.
LOG_FORMAT_JSON = os.environ.get("LOG_FORMAT_JSON", "").lower() in ("1", "true", "yes")


class JsonFormatter(logging.Formatter):
    """Structured JSON-lines formatter with pipeline correlation ID."""

    def format(self, record: logging.LogRecord) -> str:
        # Lazy import to avoid circular dependency at module load time.
        from src.etl.lineage import get_run_id

        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        run_id = get_run_id()
        if run_id:
            entry["run_id"] = run_id
        if hasattr(record, "pillar"):
            entry["pillar"] = record.pillar
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Create and return a configured logger instance.

    Parameters
    ----------
    name : str
        Logger name, typically ``__name__`` of the calling module.
    level : int, optional
        Override the default logging level.

    Returns
    -------
    logging.Logger
        Logger with console (stdout, UTF-8) and file handlers.
    """
    logger = logging.getLogger(name)

    effective_level = level or LOG_LEVEL

    # Avoid adding duplicate handlers on repeated calls.
    # Always update the level even if handlers exist.
    logger.setLevel(effective_level)
    if logger.handlers:
        return logger
    formatter: logging.Formatter
    if LOG_FORMAT_JSON:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler — explicit UTF-8 for Windows compatibility.
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(effective_level)
    console.setFormatter(formatter)
    if hasattr(console.stream, "reconfigure"):
        try:
            console.stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logger.addHandler(console)

    # File handler — persists logs to disk.
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(effective_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as exc:
        logger.warning("Could not create file handler: %s", exc)

    logger.propagate = False
    return logger


def log_section(
    logger: logging.Logger,
    title: str,
    char: str = "=",
    width: int = 60,
) -> None:
    """Log a formatted section header for visual separation.

    Parameters
    ----------
    logger : logging.Logger
        The logger instance to use.
    title : str
        The section title.
    char : str
        Separator character (default ``'='``).
    width : int
        Total width of the separator line.
    """
    separator = char * width
    logger.info(separator)
    logger.info("  %s", title)
    logger.info(separator)
