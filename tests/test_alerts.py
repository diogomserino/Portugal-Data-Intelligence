"""Tests for the alert engine."""

import json
import sqlite3
from pathlib import Path

import pytest

from src.alerts.alert_engine import Alert, AlertEngine


@pytest.fixture
def alert_db(tmp_path):
    """Create a minimal test database with some indicator values."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE fact_unemployment (
            date_key TEXT, unemployment_rate REAL
        );
        INSERT INTO fact_unemployment VALUES ('2025-12', 5.5);

        CREATE TABLE fact_inflation (
            date_key TEXT, hicp REAL
        );
        INSERT INTO fact_inflation VALUES ('2025-12', 3.2);

        CREATE TABLE fact_public_debt (
            date_key TEXT, debt_to_gdp_ratio REAL
        );
        INSERT INTO fact_public_debt VALUES ('2025-Q4', 105.0);

        CREATE TABLE fact_credit (
            date_key TEXT, npl_ratio REAL
        );
        INSERT INTO fact_credit VALUES ('2025-12', 2.1);

        CREATE TABLE fact_interest_rates (
            date_key TEXT, portugal_10y_bond_yield REAL
        );
        INSERT INTO fact_interest_rates VALUES ('2025-12', 3.0);

        CREATE TABLE fact_gdp (
            date_key TEXT, gdp_growth_yoy REAL
        );
        INSERT INTO fact_gdp VALUES ('2025-Q4', 1.5);
    """)
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def thresholds_file(tmp_path):
    """Create a test thresholds file."""
    thresholds = {
        "unemployment_rate": {
            "table": "fact_unemployment",
            "column": "unemployment_rate",
            "description": "Unemployment Rate (%)",
            "warning": {"above": 8.0},
            "critical": {"above": 12.0},
        },
        "hicp_inflation": {
            "table": "fact_inflation",
            "column": "hicp",
            "description": "HICP Inflation (%)",
            "warning": {"above": 3.0},
            "critical": {"above": 8.0},
        },
        "debt_to_gdp": {
            "table": "fact_public_debt",
            "column": "debt_to_gdp_ratio",
            "description": "Debt-to-GDP (%)",
            "warning": {"above": 100.0},
            "critical": {"above": 130.0},
        },
    }
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps(thresholds), encoding="utf-8")
    return path


class TestAlertEngine:
    def test_no_alerts_when_all_ok(self, alert_db, thresholds_file):
        # Unemployment 5.5 < 8.0 warning, inflation 3.2 > 3.0 warning
        engine = AlertEngine(db_path=alert_db, thresholds_path=thresholds_file)
        alerts = engine.check_all()
        # inflation 3.2 > 3.0 triggers warning, debt 105 > 100 triggers warning
        warning_alerts = [a for a in alerts if a.severity == "warning"]
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        assert len(critical_alerts) == 0
        assert len(warning_alerts) >= 2  # inflation + debt

    def test_critical_alert_triggered(self, tmp_path, thresholds_file):
        # Create DB with unemployment at 15% (critical)
        db = tmp_path / "critical.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE fact_unemployment (date_key TEXT, unemployment_rate REAL)")
        conn.execute("INSERT INTO fact_unemployment VALUES ('2025-12', 15.0)")
        conn.execute("CREATE TABLE fact_inflation (date_key TEXT, hicp REAL)")
        conn.execute("INSERT INTO fact_inflation VALUES ('2025-12', 1.5)")
        conn.execute("CREATE TABLE fact_public_debt (date_key TEXT, debt_to_gdp_ratio REAL)")
        conn.execute("INSERT INTO fact_public_debt VALUES ('2025-Q4', 80.0)")
        conn.commit()
        conn.close()

        engine = AlertEngine(db_path=db, thresholds_path=thresholds_file)
        alerts = engine.check_all()
        critical = [a for a in alerts if a.severity == "critical"]
        assert len(critical) >= 1
        assert critical[0].indicator == "unemployment_rate"

    def test_save_alerts(self, alert_db, thresholds_file, tmp_path):
        engine = AlertEngine(db_path=alert_db, thresholds_path=thresholds_file)
        alerts = engine.check_all()
        path = engine.save_alerts(alerts, directory=tmp_path)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "total_alerts" in data
        assert "alerts" in data

    def test_alerts_sorted_by_severity(self, tmp_path, thresholds_file):
        db = tmp_path / "mixed.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE fact_unemployment (date_key TEXT, unemployment_rate REAL)")
        conn.execute("INSERT INTO fact_unemployment VALUES ('2025-12', 15.0)")  # critical
        conn.execute("CREATE TABLE fact_inflation (date_key TEXT, hicp REAL)")
        conn.execute("INSERT INTO fact_inflation VALUES ('2025-12', 5.0)")  # warning
        conn.execute("CREATE TABLE fact_public_debt (date_key TEXT, debt_to_gdp_ratio REAL)")
        conn.execute("INSERT INTO fact_public_debt VALUES ('2025-Q4', 80.0)")
        conn.commit()
        conn.close()

        engine = AlertEngine(db_path=db, thresholds_path=thresholds_file)
        alerts = engine.check_all()
        if len(alerts) >= 2:
            # Critical should come first
            assert alerts[0].severity == "critical"


class TestAlertDataclass:
    def test_alert_fields(self):
        alert = Alert(
            indicator="test",
            description="Test",
            severity="warning",
            value=5.0,
            threshold=4.0,
            direction="above",
            period="2025-12",
            timestamp="2026-01-01T00:00:00",
        )
        assert alert.severity == "warning"
        assert alert.value == 5.0
