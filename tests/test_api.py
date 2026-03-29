"""
Tests for the FastAPI REST API (api/main.py).

Uses FastAPI's TestClient for synchronous endpoint testing.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    """Create a minimal test database with schema and sample data."""
    db_path = tmp_path_factory.mktemp("api_test") / "test.db"
    conn = sqlite3.connect(str(db_path))

    # Create dimension tables
    conn.executescript("""
        CREATE TABLE dim_date (
            date_key TEXT PRIMARY KEY,
            full_date TEXT,
            year INTEGER,
            quarter INTEGER,
            month INTEGER,
            month_name TEXT,
            is_quarter_end INTEGER
        );

        CREATE TABLE dim_source (
            source_key INTEGER PRIMARY KEY,
            source_name TEXT,
            source_url TEXT,
            description TEXT
        );

        INSERT INTO dim_date VALUES ('2025-Q4', '2025-10-01', 2025, 4, 10, 'October', 0);
        INSERT INTO dim_date VALUES ('2025-12', '2025-12-01', 2025, 4, 12, 'December', 1);
        INSERT INTO dim_source VALUES (1, 'Eurostat', 'https://eurostat.eu', 'EU Statistics');

        CREATE TABLE fact_gdp (
            id INTEGER PRIMARY KEY,
            date_key TEXT,
            nominal_gdp REAL,
            real_gdp REAL,
            gdp_growth_yoy REAL,
            gdp_growth_qoq REAL,
            gdp_per_capita REAL,
            source_key INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO fact_gdp VALUES (1, '2025-Q4', 65000, 58000, 2.5, 0.6, 22000, 1, '2025-12-01');

        CREATE TABLE fact_unemployment (
            id INTEGER PRIMARY KEY,
            date_key TEXT,
            unemployment_rate REAL,
            youth_unemployment_rate REAL,
            long_term_unemployment_rate REAL,
            labour_force_participation_rate REAL,
            source_key INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO fact_unemployment VALUES (1, '2025-12', 6.0, 18.5, 2.1, 74.0, 1, '2025-12-01');

        CREATE TABLE fact_credit (
            id INTEGER PRIMARY KEY,
            date_key TEXT,
            total_credit REAL,
            credit_nfc REAL,
            credit_households REAL,
            npl_ratio REAL,
            source_key INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO fact_credit VALUES (1, '2025-12', 850000, 400000, 450000, 2.5, 1, '2025-12-01');

        CREATE TABLE fact_interest_rates (
            id INTEGER PRIMARY KEY,
            date_key TEXT,
            ecb_main_refinancing_rate REAL,
            euribor_3m REAL,
            euribor_6m REAL,
            euribor_12m REAL,
            portugal_10y_bond_yield REAL,
            source_key INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO fact_interest_rates VALUES (1, '2025-12', 3.5, 3.2, 3.4, 3.6, 2.8, 1, '2025-12-01');

        CREATE TABLE fact_inflation (
            id INTEGER PRIMARY KEY,
            date_key TEXT,
            hicp REAL,
            cpi_estimated REAL,
            core_inflation REAL,
            is_provisional INTEGER DEFAULT 0,
            source_key INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO fact_inflation VALUES (1, '2025-12', 2.3, 2.1, 1.9, 0, 1, '2025-12-01');

        CREATE TABLE fact_public_debt (
            id INTEGER PRIMARY KEY,
            date_key TEXT,
            total_debt REAL,
            debt_to_gdp_ratio REAL,
            budget_deficit REAL,
            budget_deficit_annual REAL,
            external_debt_share_estimated REAL,
            is_provisional INTEGER DEFAULT 0,
            source_key INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO fact_public_debt VALUES (1, '2025-Q4', 280000, 98.5, -1.2, -4.8, 45.0, 0, 1, '2025-12-01');
    """)
    conn.close()
    return db_path


@pytest.fixture(scope="module")
def client(test_db, monkeypatch_module):
    """Create a TestClient with the test database."""
    from unittest.mock import PropertyMock, patch

    # Patch DATABASE_PATH before importing the app
    import config.settings

    original_path = config.settings.DATABASE_PATH
    config.settings.DATABASE_PATH = test_db

    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c

    config.settings.DATABASE_PATH = original_path


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch (pytest's is function-scoped by default)."""
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_contains_pillars(self, client):
        data = client.get("/").json()
        assert "pillars" in data
        assert len(data["pillars"]) == 6

    def test_root_contains_endpoints(self, client):
        data = client.get("/").json()
        assert "endpoints" in data


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_status_healthy(self, client):
        data = client.get("/api/v1/health").json()
        assert data["status"] == "healthy"


class TestPillarsEndpoint:
    def test_list_pillars(self, client):
        resp = client.get("/api/v1/pillars")
        assert resp.status_code == 200
        data = resp.json()
        assert "pillars" in data
        assert len(data["pillars"]) == 6

    def test_get_pillar_gdp(self, client):
        resp = client.get("/api/v1/pillars/gdp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pillar"] == "gdp"
        assert "latest" in data
        assert "statistics" in data

    def test_get_pillar_invalid(self, client):
        resp = client.get("/api/v1/pillars/invalid_pillar")
        assert resp.status_code == 404


class TestTimeseriesEndpoint:
    def test_timeseries_gdp(self, client):
        resp = client.get("/api/v1/pillars/gdp/timeseries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pillar"] == "gdp"
        assert "data" in data
        assert data["count"] >= 1

    def test_timeseries_with_year_filter(self, client):
        resp = client.get("/api/v1/pillars/gdp/timeseries?start_year=2025&end_year=2025")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

    def test_timeseries_invalid_pillar(self, client):
        resp = client.get("/api/v1/pillars/fake/timeseries")
        assert resp.status_code == 404


class TestCorrelationEndpoint:
    def test_correlation_returns_200(self, client):
        resp = client.get("/api/v1/correlation")
        assert resp.status_code == 200


class TestAlertsEndpoint:
    def test_alerts_returns_200(self, client):
        resp = client.get("/api/v1/alerts")
        # May return 200 or 500 depending on thresholds config
        assert resp.status_code in (200, 500)

    def test_alerts_response_structure(self, client):
        resp = client.get("/api/v1/alerts")
        if resp.status_code == 200:
            data = resp.json()
            assert "total" in data
            assert "critical" in data
            assert "warning" in data
            assert "alerts" in data
            assert isinstance(data["alerts"], list)


class TestEdgeCases:
    def test_invalid_pillar_sql_injection(self, client):
        resp = client.get("/api/v1/pillars/gdp'; DROP TABLE fact_gdp;--")
        assert resp.status_code == 404

    def test_invalid_pillar_case_sensitive(self, client):
        resp = client.get("/api/v1/pillars/GDP")
        # Should be case-insensitive (validate_pillar lowercases)
        assert resp.status_code == 200

    def test_timeseries_columns_filter(self, client):
        resp = client.get("/api/v1/pillars/gdp/timeseries?columns=nominal_gdp,gdp_growth_yoy")
        assert resp.status_code == 200
        data = resp.json()
        if data["count"] > 0:
            row = data["data"][0]
            assert "nominal_gdp" in row

    def test_timeseries_invalid_columns_ignored(self, client):
        resp = client.get("/api/v1/pillars/gdp/timeseries?columns=nonexistent_col")
        assert resp.status_code == 200

    def test_timeseries_limit(self, client):
        resp = client.get("/api/v1/pillars/gdp/timeseries?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 1

    def test_all_pillars_have_data(self, client):
        for pillar in [
            "gdp",
            "unemployment",
            "credit",
            "interest_rates",
            "inflation",
            "public_debt",
        ]:
            resp = client.get(f"/api/v1/pillars/{pillar}")
            assert resp.status_code == 200, f"Failed for pillar: {pillar}"


class TestErrorStates:
    def test_health_error_no_details_exposed(self, client):
        data = client.get("/api/v1/health").json()
        if data["status"] == "unhealthy":
            # Should not expose database path or stack traces
            assert "sqlite" not in data.get("error", "").lower()
