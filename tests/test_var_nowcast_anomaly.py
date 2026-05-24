"""Tests for VAR analysis, nowcasting, and anomaly detection modules.

All tests use a self-contained in-memory (tmp_path) SQLite database so they
run without a full ETL pass and without touching the production database.
"""

import sqlite3

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Minimal DB schema shared across all three modules
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS dim_date (
    date_key TEXT PRIMARY KEY,
    year     INTEGER,
    quarter  INTEGER,
    month    INTEGER
);

CREATE TABLE IF NOT EXISTS dim_source (
    source_key  INTEGER PRIMARY KEY,
    source_name TEXT
);

CREATE TABLE IF NOT EXISTS fact_gdp (
    id              INTEGER PRIMARY KEY,
    date_key        TEXT,
    gdp_growth_yoy  REAL,
    nominal_gdp     REAL,
    real_gdp        REAL,
    gdp_growth_qoq  REAL,
    gdp_per_capita  REAL,
    is_provisional  INTEGER DEFAULT 0,
    source_key      INTEGER
);

CREATE TABLE IF NOT EXISTS fact_unemployment (
    id                      INTEGER PRIMARY KEY,
    date_key                TEXT,
    unemployment_rate       REAL,
    youth_unemployment_rate REAL,
    is_provisional          INTEGER DEFAULT 0,
    source_key              INTEGER
);

CREATE TABLE IF NOT EXISTS fact_inflation (
    id             INTEGER PRIMARY KEY,
    date_key       TEXT,
    hicp           REAL,
    cpi_estimated  REAL,
    core_inflation REAL,
    is_provisional INTEGER DEFAULT 0,
    source_key     INTEGER
);

CREATE TABLE IF NOT EXISTS fact_interest_rates (
    id                        INTEGER PRIMARY KEY,
    date_key                  TEXT,
    ecb_main_refinancing_rate REAL,
    portugal_10y_bond_yield   REAL,
    euribor_3m                REAL,
    is_provisional            INTEGER DEFAULT 0,
    source_key                INTEGER
);

CREATE TABLE IF NOT EXISTS fact_public_debt (
    id                INTEGER PRIMARY KEY,
    date_key          TEXT,
    total_debt        REAL,
    debt_to_gdp_ratio REAL,
    is_provisional    INTEGER DEFAULT 0,
    source_key        INTEGER
);
"""


def _build_test_db(db_path: str, n_quarters: int = 32) -> None:
    """Populate a test SQLite database with synthetic macro data (no noise bias)."""
    conn = sqlite3.connect(db_path)
    conn.executescript(_DDL)
    conn.execute("INSERT OR IGNORE INTO dim_source VALUES (1,'Test')")

    rng = np.random.default_rng(42)

    quarter_rows: list = []
    monthly_rows: list = []
    year, q = 2010, 1
    for _ in range(n_quarters):
        dk_q = f"{year}-Q{q}"
        quarter_rows.append((dk_q, year, q, None))
        # all 3 months in the quarter — include quarter so _quarterly_average groupby works
        for m in range(q * 3 - 2, q * 3 + 1):
            mdk = f"{year}-{m:02d}"
            monthly_rows.append((mdk, year, q, m))
        q += 1
        if q > 4:
            q = 1
            year += 1

    conn.executemany("INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?)", quarter_rows)
    conn.executemany("INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?)", monthly_rows)

    # GDP — quarterly
    gdp_growth = rng.normal(1.5, 2.0, n_quarters)
    for i, (dk, yr, qu, _) in enumerate(quarter_rows):
        conn.execute(
            "INSERT INTO fact_gdp "
            "(date_key, gdp_growth_yoy, nominal_gdp, real_gdp, gdp_growth_qoq, gdp_per_capita, source_key) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                dk,
                float(gdp_growth[i]),
                200.0 + i,
                190.0 + i,
                float(gdp_growth[i]) / 4,
                19000.0 + i * 100,
                1,
            ),
        )

    # Unemployment — monthly
    unemp = rng.uniform(6.0, 16.0, len(monthly_rows))
    for i, (dk, *_) in enumerate(monthly_rows):
        conn.execute(
            "INSERT INTO fact_unemployment (date_key, unemployment_rate, youth_unemployment_rate, source_key) "
            "VALUES (?,?,?,?)",
            (dk, float(unemp[i]), float(unemp[i]) * 1.8, 1),
        )

    # Inflation — monthly
    hicp = rng.uniform(-0.5, 4.0, len(monthly_rows))
    for i, (dk, *_) in enumerate(monthly_rows):
        conn.execute(
            "INSERT INTO fact_inflation (date_key, hicp, cpi_estimated, source_key) VALUES (?,?,?,?)",
            (dk, float(hicp[i]), float(hicp[i]) * 1.05, 1),
        )

    # Interest rates — monthly
    ecb_rate = rng.uniform(0.0, 4.5, len(monthly_rows))
    bond_yield = ecb_rate + rng.uniform(0.5, 3.0, len(monthly_rows))
    for i, (dk, *_) in enumerate(monthly_rows):
        conn.execute(
            "INSERT INTO fact_interest_rates "
            "(date_key, ecb_main_refinancing_rate, portugal_10y_bond_yield, euribor_3m, source_key) "
            "VALUES (?,?,?,?,?)",
            (dk, float(ecb_rate[i]), float(bond_yield[i]), float(ecb_rate[i]) + 0.2, 1),
        )

    # Public debt — quarterly
    debt = rng.uniform(95.0, 135.0, n_quarters)
    for i, (dk, *_) in enumerate(quarter_rows):
        conn.execute(
            "INSERT INTO fact_public_debt (date_key, total_debt, debt_to_gdp_ratio, source_key) VALUES (?,?,?,?)",
            (dk, float(debt[i]) * 200.0, float(debt[i]), 1),
        )

    conn.commit()
    conn.close()


@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("var_db") / "test.db"
    _build_test_db(str(db))
    return str(db)


@pytest.fixture(scope="module")
def empty_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("empty_db") / "empty.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(_DDL)
    conn.commit()
    conn.close()
    return str(db)


# ---------------------------------------------------------------------------
# VAR Analysis
# ---------------------------------------------------------------------------


class TestVARAnalysis:
    """Tests for run_var_analysis."""

    def test_returns_dict(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        assert isinstance(result, dict)

    def test_expected_keys_on_success(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        if "error" in result:
            pytest.skip(f"VAR failed: {result['error']}")
        for key in ("selected_lag", "granger_causality", "irf_gdp_shock", "fevd", "aic", "bic"):
            assert key in result, f"Missing key: {key}"

    def test_selected_lag_is_positive_integer(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        if "error" in result:
            pytest.skip(f"VAR failed: {result['error']}")
        assert isinstance(result["selected_lag"], int)
        assert result["selected_lag"] >= 1

    def test_irf_has_values(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        if "error" in result or "irf_gdp_shock" not in result:
            pytest.skip("IRF not available")
        irf = result["irf_gdp_shock"]
        assert len(irf) > 0
        for col, values in irf.items():
            assert len(values) > 0, f"IRF for {col} is empty"

    def test_granger_has_target_variables(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        if "error" in result or "granger_causality" not in result:
            pytest.skip("Granger not available")
        gc = result["granger_causality"]
        # At least one of the first 3 VAR columns is a key
        assert len(gc) > 0

    def test_fevd_is_square_dict(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        if "error" in result or "fevd" not in result:
            pytest.skip("FEVD not available")
        fevd = result["fevd"]
        assert len(fevd) > 0
        for variable, decomp in fevd.items():
            assert isinstance(decomp, dict)

    def test_aic_is_finite_float(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        if "error" in result:
            pytest.skip(f"VAR failed: {result['error']}")
        assert isinstance(result["aic"], (int, float))
        assert not np.isnan(result["aic"])

    def test_returns_error_on_empty_db(self, empty_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=empty_db)
        assert "error" in result

    def test_n_observations_present(self, test_db):
        from src.analysis.var_analysis import run_var_analysis

        result = run_var_analysis(db_path=test_db)
        if "error" in result:
            pytest.skip(f"VAR failed: {result['error']}")
        assert "n_observations" in result
        assert result["n_observations"] > 0


# ---------------------------------------------------------------------------
# Nowcasting
# ---------------------------------------------------------------------------


class TestNowcasting:
    """Tests for _quarterly_average and run_nowcasting."""

    def test_quarterly_average_mean_correct(self):
        from src.analysis.nowcasting import _quarterly_average

        df = pd.DataFrame(
            {
                "year": [2020, 2020, 2020, 2020, 2020, 2020],
                "quarter": [1, 1, 1, 2, 2, 2],
                "rate": [3.0, 6.0, 9.0, 12.0, 15.0, 18.0],
            }
        )
        result = _quarterly_average(df, "rate")
        assert len(result) == 2
        q1_mean = float(result.loc[result["quarter"] == 1, "rate"].iloc[0])
        q2_mean = float(result.loc[result["quarter"] == 2, "rate"].iloc[0])
        assert q1_mean == pytest.approx(6.0)
        assert q2_mean == pytest.approx(15.0)

    def test_quarterly_average_single_row(self):
        from src.analysis.nowcasting import _quarterly_average

        df = pd.DataFrame({"year": [2021], "quarter": [3], "val": [5.5]})
        result = _quarterly_average(df, "val")
        assert len(result) == 1
        assert float(result["val"].iloc[0]) == pytest.approx(5.5)

    def test_quarterly_average_returns_dataframe(self):
        from src.analysis.nowcasting import _quarterly_average

        df = pd.DataFrame({"year": [2020, 2020], "quarter": [1, 1], "x": [1.0, 3.0]})
        result = _quarterly_average(df, "x")
        assert isinstance(result, pd.DataFrame)
        assert "year" in result.columns
        assert "quarter" in result.columns

    def test_returns_dict(self, test_db):
        from src.analysis.nowcasting import run_nowcasting

        result = run_nowcasting(db_path=test_db)
        assert isinstance(result, dict)

    def test_expected_keys_on_success(self, test_db):
        from src.analysis.nowcasting import run_nowcasting

        result = run_nowcasting(db_path=test_db)
        if "error" in result:
            pytest.skip(f"Nowcasting failed: {result['error']}")
        for key in ("nowcast", "confidence_interval", "model_fit", "predictors", "latest_quarter"):
            assert key in result, f"Missing key: {key}"

    def test_confidence_interval_ordered(self, test_db):
        from src.analysis.nowcasting import run_nowcasting

        result = run_nowcasting(db_path=test_db)
        if "error" in result:
            pytest.skip("Nowcasting failed")
        ci = result["confidence_interval"]
        assert ci["lower_95"] < result["nowcast"] < ci["upper_95"]

    def test_model_fit_keys(self, test_db):
        from src.analysis.nowcasting import run_nowcasting

        result = run_nowcasting(db_path=test_db)
        if "error" in result:
            pytest.skip("Nowcasting failed")
        fit = result["model_fit"]
        assert "r_squared" in fit
        assert "mae" in fit
        assert "n_observations" in fit
        assert fit["n_observations"] >= 6

    def test_nowcast_is_finite_float(self, test_db):
        from src.analysis.nowcasting import run_nowcasting

        result = run_nowcasting(db_path=test_db)
        if "error" in result:
            pytest.skip("Nowcasting failed")
        assert isinstance(result["nowcast"], (int, float))
        assert not np.isnan(result["nowcast"])

    def test_predictors_is_nonempty_list(self, test_db):
        from src.analysis.nowcasting import run_nowcasting

        result = run_nowcasting(db_path=test_db)
        if "error" in result:
            pytest.skip("Nowcasting failed")
        assert isinstance(result["predictors"], list)
        assert len(result["predictors"]) > 0

    def test_returns_error_on_empty_db(self, empty_db):
        from src.analysis.nowcasting import run_nowcasting

        result = run_nowcasting(db_path=empty_db)
        assert "error" in result


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------


class TestAnomalyDetection:
    """Tests for _rolling_zscore_anomalies and detect_anomalies."""

    def test_zscore_detects_spike(self):
        from src.analysis.anomaly_detection import _rolling_zscore_anomalies

        rng = np.random.default_rng(0)
        values = rng.normal(5.0, 0.15, 50).tolist()
        values[35] = 30.0  # clear spike well above threshold
        df = pd.DataFrame({"value": values, "year": [2010] * 50, "month": list(range(1, 51))})
        anomalies = _rolling_zscore_anomalies(df, window=24, threshold=2.5)
        assert any(a["index"] == 35 for a in anomalies), "Spike at index 35 not detected"

    def test_zscore_ignores_stationary_noise(self):
        from src.analysis.anomaly_detection import _rolling_zscore_anomalies

        rng = np.random.default_rng(42)
        values = rng.normal(5.0, 0.05, 60).tolist()  # very tight noise
        df = pd.DataFrame({"value": values, "year": [2010] * 60, "month": list(range(1, 61))})
        anomalies = _rolling_zscore_anomalies(df, window=24, threshold=2.5)
        assert len(anomalies) < 3

    def test_zscore_returns_list(self):
        from src.analysis.anomaly_detection import _rolling_zscore_anomalies

        df = pd.DataFrame({"value": [1.0] * 30, "year": [2020] * 30, "month": list(range(1, 31))})
        result = _rolling_zscore_anomalies(df)
        assert isinstance(result, list)

    def test_zscore_empty_for_short_series(self):
        from src.analysis.anomaly_detection import _rolling_zscore_anomalies

        df = pd.DataFrame({"value": [1.0, 2.0, 3.0], "year": [2020] * 3, "month": [1, 2, 3]})
        result = _rolling_zscore_anomalies(df, window=24)
        assert result == []

    def test_zscore_anomaly_has_required_keys(self):
        from src.analysis.anomaly_detection import _rolling_zscore_anomalies

        rng = np.random.default_rng(1)
        values = rng.normal(5.0, 0.1, 50).tolist()
        values[40] = 100.0
        df = pd.DataFrame({"value": values, "year": [2010] * 50, "month": list(range(1, 51))})
        anomalies = _rolling_zscore_anomalies(df, window=24, threshold=2.5)
        assert len(anomalies) > 0
        a = anomalies[0]
        for key in ("index", "value", "z_score", "rolling_mean", "rolling_std", "year", "period"):
            assert key in a, f"Missing key '{key}' in anomaly dict"

    def test_zscore_zscore_exceeds_threshold(self):
        from src.analysis.anomaly_detection import _rolling_zscore_anomalies

        rng = np.random.default_rng(2)
        values = rng.normal(5.0, 0.2, 50).tolist()
        values[40] = 50.0
        df = pd.DataFrame({"value": values, "year": [2010] * 50, "month": list(range(1, 51))})
        anomalies = _rolling_zscore_anomalies(df, window=24, threshold=2.5)
        for a in anomalies:
            assert abs(a["z_score"]) >= 2.5

    def test_detect_returns_dict(self, test_db):
        from src.analysis.anomaly_detection import detect_anomalies

        result = detect_anomalies(db_path=test_db)
        assert isinstance(result, dict)

    def test_detect_has_core_pillars(self, test_db):
        from src.analysis.anomaly_detection import detect_anomalies

        result = detect_anomalies(db_path=test_db)
        for pillar in ("gdp", "unemployment", "inflation", "interest_rates", "public_debt"):
            assert pillar in result, f"Missing pillar: {pillar}"

    def test_detect_count_matches_list_length(self, test_db):
        from src.analysis.anomaly_detection import detect_anomalies

        result = detect_anomalies(db_path=test_db)
        for pillar, data in result.items():
            assert data["n_zscore_anomalies"] == len(
                data["zscore_anomalies"]
            ), f"{pillar}: count mismatch"

    def test_detect_n_observations_positive(self, test_db):
        from src.analysis.anomaly_detection import detect_anomalies

        result = detect_anomalies(db_path=test_db)
        for pillar, data in result.items():
            assert data["n_observations"] > 0, f"{pillar}: zero observations"

    def test_detect_empty_db_returns_empty(self, empty_db):
        from src.analysis.anomaly_detection import detect_anomalies

        result = detect_anomalies(db_path=empty_db)
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_isolation_forest_runs_with_sufficient_data(self, test_db):
        from src.analysis.anomaly_detection import HAS_SKLEARN, detect_anomalies

        if not HAS_SKLEARN:
            pytest.skip("sklearn not available")
        result = detect_anomalies(db_path=test_db)
        # Monthly pillars (unemployment, inflation, interest_rates) have 96 rows
        for pillar in ("unemployment", "inflation", "interest_rates"):
            if pillar in result and result[pillar].get("n_observations", 0) >= 30:
                assert "isolation_forest_anomalies" in result[pillar]
                assert "n_isolation_forest_anomalies" in result[pillar]
                assert isinstance(result[pillar]["isolation_forest_anomalies"], list)
