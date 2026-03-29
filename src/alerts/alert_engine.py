"""
Portugal Data Intelligence — Alert Engine
============================================
Monitors macroeconomic indicators against configurable thresholds
and generates alerts when values breach warning or critical levels.

Usage:
    from src.alerts.alert_engine import AlertEngine
    engine = AlertEngine()
    alerts = engine.check_all()
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import CONFIG_DIR, DATABASE_PATH, REPORTS_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

THRESHOLDS_FILE = CONFIG_DIR / "alert_thresholds.json"
ALERTS_DIR = REPORTS_DIR / "alerts"

# Whitelist of valid tables and columns to prevent SQL injection
_VALID_TABLES = frozenset(
    {
        "fact_gdp",
        "fact_unemployment",
        "fact_inflation",
        "fact_public_debt",
        "fact_credit",
        "fact_interest_rates",
    }
)
_VALID_COLUMNS = frozenset(
    {
        "gdp_growth_yoy",
        "unemployment_rate",
        "hicp",
        "debt_to_gdp_ratio",
        "npl_ratio",
        "portugal_10y_bond_yield",
        "nominal_gdp",
        "real_gdp",
        "gdp_per_capita",
        "youth_unemployment_rate",
        "long_term_unemployment_rate",
        "labour_force_participation_rate",
        "total_credit",
        "credit_nfc",
        "credit_households",
        "ecb_main_refinancing_rate",
        "euribor_3m",
        "euribor_6m",
        "euribor_12m",
        "cpi_estimated",
        "core_inflation",
        "total_debt",
        "budget_deficit",
        "budget_deficit_annual",
        "external_debt_share_estimated",
    }
)


@dataclass
class Alert:
    """A single threshold breach alert."""

    indicator: str
    description: str
    severity: str  # warning | critical
    value: float
    threshold: float
    direction: str  # above | below
    period: str
    timestamp: str


class AlertEngine:
    """Check latest indicator values against configurable thresholds.

    Parameters
    ----------
    db_path : Path, optional
        Override the default database path.
    thresholds_path : Path, optional
        Override the default thresholds JSON file.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        thresholds_path: Optional[Path] = None,
    ):
        self.db_path = db_path or DATABASE_PATH
        self.thresholds_path = thresholds_path or THRESHOLDS_FILE
        self.thresholds = self._load_thresholds()

    def _load_thresholds(self) -> Dict[str, Any]:
        """Load threshold definitions from JSON."""
        if not self.thresholds_path.exists():
            logger.error("Thresholds file not found: %s", self.thresholds_path)
            return {}
        try:
            with open(self.thresholds_path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load thresholds: %s", exc)
            return {}

    @staticmethod
    def _validate_identifier(value: str, allowed: frozenset) -> bool:
        """Validate that an SQL identifier is in the allowed whitelist."""
        return value in allowed

    def _get_latest_value(
        self, conn: sqlite3.Connection, table: str, column: str
    ) -> Optional[tuple]:  # type: ignore[type-arg]
        """Return (date_key, value) for the most recent non-null observation."""
        if not self._validate_identifier(table, _VALID_TABLES):
            logger.error("Invalid table name rejected: %s", table)
            return None
        if not self._validate_identifier(column, _VALID_COLUMNS):
            logger.error("Invalid column name rejected: %s", column)
            return None
        try:
            row = conn.execute(
                f"SELECT date_key, {column} FROM {table} "
                f"WHERE {column} IS NOT NULL ORDER BY date_key DESC LIMIT 1"
            ).fetchone()
            return row  # type: ignore[return-value,no-any-return]
        except sqlite3.Error as exc:
            logger.warning("Could not query %s.%s: %s", table, column, exc)
            return None

    def _check_indicator(
        self,
        indicator_key: str,
        config: Dict[str, Any],
        conn: sqlite3.Connection,
    ) -> List[Alert]:
        """Check a single indicator against its thresholds."""
        result = self._get_latest_value(conn, config["table"], config["column"])
        if result is None:
            return []

        date_key, value = result
        if value is None:
            return []

        alerts = []
        now = datetime.now(timezone.utc).isoformat()

        for severity in ("critical", "warning"):
            rules = config.get(severity, {})
            if not isinstance(rules, dict):
                logger.warning(
                    "Invalid rules for %s/%s — expected dict, got %s",
                    indicator_key,
                    severity,
                    type(rules).__name__,
                )
                continue
            if "above" in rules and not isinstance(rules["above"], (int, float)):
                logger.warning("Non-numeric 'above' threshold for %s/%s", indicator_key, severity)
                continue
            if "below" in rules and not isinstance(rules["below"], (int, float)):
                logger.warning("Non-numeric 'below' threshold for %s/%s", indicator_key, severity)
                continue
            if "above" in rules and value > rules["above"]:
                alerts.append(
                    Alert(
                        indicator=indicator_key,
                        description=config["description"],
                        severity=severity,
                        value=round(float(value), 2),
                        threshold=rules["above"],
                        direction="above",
                        period=str(date_key),
                        timestamp=now,
                    )
                )
            if "below" in rules and value < rules["below"]:
                alerts.append(
                    Alert(
                        indicator=indicator_key,
                        description=config["description"],
                        severity=severity,
                        value=round(float(value), 2),
                        threshold=rules["below"],
                        direction="below",
                        period=str(date_key),
                        timestamp=now,
                    )
                )

        return alerts

    def check_all(self) -> List[Alert]:
        """Check all configured indicators and return any alerts.

        Returns
        -------
        list of Alert
            All triggered alerts, sorted by severity (critical first).
        """
        conn = sqlite3.connect(str(self.db_path))
        all_alerts: List[Alert] = []
        try:
            for key, config in self.thresholds.items():
                alerts = self._check_indicator(key, config, conn)
                for alert in alerts:
                    log_fn = logger.critical if alert.severity == "critical" else logger.warning
                    log_fn(
                        "ALERT [%s] %s: %s = %.2f (threshold: %s %.2f)",
                        alert.severity.upper(),
                        alert.indicator,
                        alert.description,
                        alert.value,
                        alert.direction,
                        alert.threshold,
                    )
                all_alerts.extend(alerts)
        finally:
            conn.close()

        # Sort: critical first, then warning
        severity_order = {"critical": 0, "warning": 1}
        all_alerts.sort(key=lambda a: severity_order.get(a.severity, 2))

        logger.info("Alert check complete: %d alert(s) triggered", len(all_alerts))
        return all_alerts

    def save_alerts(self, alerts: List[Alert], directory: Optional[Path] = None) -> Path:
        """Save alerts to a timestamped JSON file."""
        out_dir = directory or ALERTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"alerts_{ts}.json"

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_alerts": len(alerts),
            "critical": sum(1 for a in alerts if a.severity == "critical"),
            "warning": sum(1 for a in alerts if a.severity == "warning"),
            "alerts": [asdict(a) for a in alerts],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Alerts saved to %s", path)
        return path
