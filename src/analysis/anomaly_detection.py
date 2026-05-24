"""
Portugal Data Intelligence - Anomaly Detection
===============================================
Detects statistical anomalies in macroeconomic time series using:
  1. Rolling z-score (window=24 months) for per-series outlier detection
  2. Isolation Forest for multivariate anomaly detection

Usage:
    from src.analysis.anomaly_detection import detect_anomalies
    results = detect_anomalies()
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from sklearn.ensemble import IsolationForest

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

_Z_SCORE_WINDOW = 24
_Z_SCORE_THRESHOLD = 2.5  # flag observations beyond 2.5 sigma

_PILLAR_QUERIES = {
    "gdp": (
        "SELECT d.year, d.quarter, f.gdp_growth_yoy AS value "
        "FROM fact_gdp f JOIN dim_date d ON f.date_key=d.date_key "
        "WHERE f.gdp_growth_yoy IS NOT NULL ORDER BY d.year, d.quarter"
    ),
    "unemployment": (
        "SELECT d.year, d.month, f.unemployment_rate AS value "
        "FROM fact_unemployment f JOIN dim_date d ON f.date_key=d.date_key "
        "WHERE f.unemployment_rate IS NOT NULL ORDER BY d.year, d.month"
    ),
    "inflation": (
        "SELECT d.year, d.month, f.hicp AS value "
        "FROM fact_inflation f JOIN dim_date d ON f.date_key=d.date_key "
        "WHERE f.hicp IS NOT NULL ORDER BY d.year, d.month"
    ),
    "interest_rates": (
        "SELECT d.year, d.month, f.portugal_10y_bond_yield AS value "
        "FROM fact_interest_rates f JOIN dim_date d ON f.date_key=d.date_key "
        "WHERE f.portugal_10y_bond_yield IS NOT NULL ORDER BY d.year, d.month"
    ),
    "public_debt": (
        "SELECT d.year, d.quarter, f.debt_to_gdp_ratio AS value "
        "FROM fact_public_debt f JOIN dim_date d ON f.date_key=d.date_key "
        "WHERE f.debt_to_gdp_ratio IS NOT NULL ORDER BY d.year, d.quarter"
    ),
}


def _rolling_zscore_anomalies(
    df: pd.DataFrame, window: int = _Z_SCORE_WINDOW, threshold: float = _Z_SCORE_THRESHOLD
) -> List[dict]:
    """Flag observations where the rolling z-score exceeds threshold."""
    values = df["value"].values.astype(float)
    n = len(values)
    anomalies = []

    for i in range(window, n):
        window_vals = values[i - window : i]
        mean = np.mean(window_vals)
        std = np.std(window_vals, ddof=1)
        if std < 1e-10:
            continue
        z = (values[i] - mean) / std
        if abs(z) >= threshold:
            row = df.iloc[i]
            anomalies.append(
                {
                    "index": i,
                    "value": round(float(values[i]), 4),
                    "z_score": round(float(z), 2),
                    "rolling_mean": round(float(mean), 4),
                    "rolling_std": round(float(std), 4),
                    "year": int(row.get("year", 0)),
                    "period": int(row.get("month", row.get("quarter", 0))),
                }
            )

    return anomalies


def detect_anomalies(db_path: Optional[str] = None) -> Dict[str, dict]:
    """Run anomaly detection for all configured pillars.

    Returns
    -------
    dict
        Keys are pillar names. Values contain 'zscore_anomalies' list
        and optionally 'isolation_forest_anomalies'.
    """
    db_path = db_path or str(DATABASE_PATH)
    results = {}

    with get_connection(db_path) as conn:
        for pillar, query in _PILLAR_QUERIES.items():
            try:
                df = pd.read_sql(query, conn)
            except Exception as exc:
                logger.warning(f"Cannot load {pillar} for anomaly detection: {exc}")
                continue

            if df.empty or "value" not in df.columns:
                continue

            # Rolling z-score
            zscore_anomalies = _rolling_zscore_anomalies(df)

            pillar_result: dict = {
                "n_observations": len(df),
                "zscore_anomalies": zscore_anomalies,
                "n_zscore_anomalies": len(zscore_anomalies),
            }

            # Isolation Forest (if sklearn available and enough data)
            if HAS_SKLEARN and len(df) >= 30:
                try:
                    X = df["value"].values.reshape(-1, 1)
                    iso = IsolationForest(contamination=0.05, random_state=42)
                    labels = iso.fit_predict(X)
                    iso_anomaly_indices = [i for i, lbl in enumerate(labels) if lbl == -1]
                    pillar_result["isolation_forest_anomalies"] = iso_anomaly_indices
                    pillar_result["n_isolation_forest_anomalies"] = len(iso_anomaly_indices)
                except Exception as exc:
                    logger.warning(f"Isolation Forest failed for {pillar}: {exc}")

            results[pillar] = pillar_result
            logger.info(f"{pillar}: {len(zscore_anomalies)} z-score anomalies detected")

    return results
