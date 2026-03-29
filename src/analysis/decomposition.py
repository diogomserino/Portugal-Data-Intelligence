"""
Portugal Data Intelligence — Seasonal Decomposition Module
============================================================
Applies STL (Seasonal and Trend decomposition using Loess) to
macroeconomic time series and produces 3-panel diagnostic charts.

Requires ``statsmodels>=0.14.0``.

Usage:
    from src.analysis.decomposition import decompose_and_plot
    result = decompose_and_plot(series, period=12, title="Unemployment")
"""

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from config.settings import DATABASE_PATH, POWERBI_DIR
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)

try:
    from statsmodels.tsa.seasonal import STL

    HAS_STL = True
except ImportError:
    HAS_STL = False


def decompose_series(
    series: pd.Series,
    period: int = 12,
    robust: bool = True,
) -> Optional[Dict[str, np.ndarray]]:
    """Run STL decomposition on a time series.

    Parameters
    ----------
    series : pd.Series
        The time series (oldest-first, no NaNs).
    period : int
        Seasonal period (4 for quarterly, 12 for monthly).
    robust : bool
        Use robust fitting to reduce influence of outliers.

    Returns
    -------
    dict or None
        Keys: ``trend``, ``seasonal``, ``residual``, ``observed``.
        Returns None if statsmodels is unavailable or the series is
        too short for decomposition.
    """
    if not HAS_STL:
        logger.warning("statsmodels not installed — STL decomposition unavailable")
        return None

    clean = series.dropna()
    if len(clean) < 2 * period + 1:
        logger.warning("Series too short for STL (need >= %d, got %d)", 2 * period + 1, len(clean))
        return None

    stl = STL(clean, period=period, robust=robust)
    result = stl.fit()

    return {
        "observed": np.array(result.observed),
        "trend": np.array(result.trend),
        "seasonal": np.array(result.seasonal),
        "residual": np.array(result.resid),
    }


def plot_decomposition(
    components: Dict[str, np.ndarray],
    title: str,
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    """Generate a 3-panel decomposition chart (trend, seasonal, residual).

    Parameters
    ----------
    components : dict
        Output from :func:`decompose_series`.
    title : str
        Chart title.
    output_path : Path, optional
        Override destination file path.

    Returns
    -------
    Path or None
        Path to the saved PNG, or None on failure.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available — skipping decomposition chart")
        return None

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f"STL Decomposition — {title}", fontsize=14, fontweight="bold")

    labels = ["Observed", "Trend", "Seasonal", "Residual"]
    keys = ["observed", "trend", "seasonal", "residual"]
    colors = ["#2c3e50", "#2980b9", "#27ae60", "#e74c3c"]

    for ax, label, key, color in zip(axes, labels, keys, colors):
        ax.plot(components[key], color=color, linewidth=1.0)
        ax.set_ylabel(label, fontsize=10)
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel("Observation", fontsize=10)
    plt.tight_layout(rect=(0, 0, 1, 0.96))  # type: ignore[arg-type]

    if output_path is None:
        safe_name = title.lower().replace(" ", "_").replace("/", "_")
        output_path = POWERBI_DIR / "charts" / f"stl_{safe_name}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Decomposition chart saved: %s", output_path)
    return output_path


def decompose_and_plot(
    series: pd.Series,
    period: int = 12,
    title: str = "Time Series",
    output_path: Optional[Path] = None,
) -> Optional[Dict[str, np.ndarray]]:
    """Decompose a series and generate the chart in one call."""
    components = decompose_series(series, period=period)
    if components is not None:
        plot_decomposition(components, title=title, output_path=output_path)
    return components


def run_decomposition(db_path: Optional[str] = None) -> Dict[str, Optional[Dict[str, np.ndarray]]]:
    """Run STL decomposition on the main pillar series from the database.

    Returns
    -------
    dict
        Pillar name -> decomposition components (or None if failed).
    """
    from src.utils.db import get_connection

    log_section(logger, "STL DECOMPOSITION")

    results = {}
    with get_connection(db_path) as conn:
        # Unemployment (monthly, period=12)
        try:
            unemp = pd.read_sql(
                "SELECT unemployment_rate FROM fact_unemployment ORDER BY date_key",
                conn,
            )["unemployment_rate"]
            results["unemployment"] = decompose_and_plot(
                unemp, period=12, title="Unemployment Rate"
            )
        except Exception as exc:
            logger.error("Unemployment decomposition failed: %s", exc)
            results["unemployment"] = None

        # Inflation (monthly, period=12)
        try:
            infl = pd.read_sql("SELECT hicp FROM fact_inflation ORDER BY date_key", conn)["hicp"]
            results["inflation"] = decompose_and_plot(infl, period=12, title="HICP Inflation")
        except Exception as exc:
            logger.error("Inflation decomposition failed: %s", exc)
            results["inflation"] = None

        # GDP (quarterly, period=4)
        try:
            gdp = pd.read_sql("SELECT real_gdp FROM fact_gdp ORDER BY date_key", conn)["real_gdp"]
            results["gdp"] = decompose_and_plot(gdp, period=4, title="Real GDP")
        except Exception as exc:
            logger.error("GDP decomposition failed: %s", exc)
            results["gdp"] = None
    logger.info("STL decomposition complete — %d pillars processed", len(results))
    return results
