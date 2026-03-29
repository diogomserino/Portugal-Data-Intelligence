"""
Portugal Data Intelligence - EU Benchmark Data Generation
==========================================================
Generates realistic synthetic macroeconomic benchmark data for key EU
peer countries and European averages (2010-2025).

Countries/aggregates:
    PT  - Portugal (pulled from existing database where possible)
    DE  - Germany
    ES  - Spain
    FR  - France
    IT  - Italy
    EU_AVG - EU-27 average
    EA_AVG - Euro Area average

Indicators (annual):
    gdp_growth        - Real GDP growth rate (% YoY)
    unemployment      - Unemployment rate (%)
    inflation         - HICP inflation rate (%)
    debt_to_gdp       - General government debt as % of GDP
    interest_rate_10y - 10-year sovereign bond yield (%)

Approach:
    1. Define annual reference points from actual/realistic data per country.
    2. Use numpy linear interpolation (np.interp) to fill intermediate years.
    3. Add controlled random noise for realism.
    4. Save to data/raw/raw_eu_benchmark.csv and load into the database.

All random operations use seed 43 for full reproducibility.

Author: Portugal Data Intelligence
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (
    DATABASE_DIR,
    DATABASE_PATH,
    DDL_DIR,
    END_YEAR,
    RAW_DATA_DIR,
    START_YEAR,
    ensure_directories,
)
from src.utils.logger import get_logger, log_section

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = get_logger("generate_eu_benchmark")

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RNG_SEED = 43
rng = np.random.default_rng(RNG_SEED)

# ---------------------------------------------------------------------------
# Year range
# ---------------------------------------------------------------------------
YEARS = list(range(START_YEAR, END_YEAR + 1))  # 2010-2025

# ---------------------------------------------------------------------------
# Country definitions
# ---------------------------------------------------------------------------
COUNTRIES = {
    "PT": "Portugal",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "IT": "Italy",
    "EU_AVG": "EU-27 Average",
    "EA_AVG": "Euro Area Average",
}

# ---------------------------------------------------------------------------
# Reference data points per country and indicator
# ---------------------------------------------------------------------------
# Format: {country_code: {indicator: {year: value, ...}}}
# These are realistic reference points; np.interp fills intermediate years.

REFERENCE_DATA = {
    "PT": {
        "gdp_growth": {
            2010: 1.7,
            2011: -1.7,
            2012: -4.1,
            2013: -0.9,
            2014: 0.8,
            2015: 1.8,
            2016: 2.0,
            2017: 3.5,
            2018: 2.8,
            2019: 2.7,
            2020: -8.3,
            2021: 5.5,
            2022: 6.8,
            2023: 2.3,
            2024: 1.8,
            2025: 2.0,
        },
        "unemployment": {
            2010: 12.0,
            2011: 12.9,
            2012: 15.8,
            2013: 16.4,
            2014: 14.1,
            2015: 12.6,
            2016: 11.2,
            2017: 9.0,
            2018: 7.0,
            2019: 6.5,
            2020: 7.0,
            2021: 6.6,
            2022: 6.0,
            2023: 6.5,
            2024: 6.4,
            2025: 6.2,
        },
        "inflation": {
            2010: 1.4,
            2011: 3.6,
            2012: 2.8,
            2013: 0.4,
            2014: -0.2,
            2015: 0.5,
            2016: 0.6,
            2017: 1.6,
            2018: 1.2,
            2019: 0.3,
            2020: -0.1,
            2021: 0.9,
            2022: 8.1,
            2023: 5.3,
            2024: 2.6,
            2025: 2.1,
        },
        "debt_to_gdp": {
            2010: 96.2,
            2011: 111.4,
            2012: 126.2,
            2013: 129.0,
            2014: 130.6,
            2015: 128.8,
            2016: 131.5,
            2017: 126.1,
            2018: 121.5,
            2019: 116.6,
            2020: 134.9,
            2021: 125.4,
            2022: 113.9,
            2023: 99.1,
            2024: 95.7,
            2025: 93.0,
        },
        "interest_rate_10y": {
            2010: 5.4,
            2011: 10.2,
            2012: 10.6,
            2013: 6.3,
            2014: 3.7,
            2015: 2.4,
            2016: 3.2,
            2017: 3.1,
            2018: 1.8,
            2019: 0.4,
            2020: 0.4,
            2021: 0.4,
            2022: 2.9,
            2023: 3.1,
            2024: 3.0,
            2025: 2.8,
        },
    },
    "DE": {
        "gdp_growth": {
            2010: 4.2,
            2011: 3.9,
            2012: 0.4,
            2013: 0.4,
            2014: 2.2,
            2015: 1.5,
            2016: 2.2,
            2017: 2.7,
            2018: 1.0,
            2019: 1.1,
            2020: -3.8,
            2021: 3.2,
            2022: 1.8,
            2023: -0.1,
            2024: 0.2,
            2025: 0.8,
        },
        "unemployment": {
            2010: 7.0,
            2011: 5.8,
            2012: 5.4,
            2013: 5.2,
            2014: 5.0,
            2015: 4.6,
            2016: 4.1,
            2017: 3.8,
            2018: 3.4,
            2019: 3.1,
            2020: 3.8,
            2021: 3.6,
            2022: 3.1,
            2023: 3.0,
            2024: 3.2,
            2025: 3.4,
        },
        "inflation": {
            2010: 1.1,
            2011: 2.5,
            2012: 2.1,
            2013: 1.6,
            2014: 0.8,
            2015: 0.7,
            2016: 0.4,
            2017: 1.7,
            2018: 1.9,
            2019: 1.4,
            2020: 0.4,
            2021: 3.2,
            2022: 8.7,
            2023: 6.0,
            2024: 2.4,
            2025: 2.0,
        },
        "debt_to_gdp": {
            2010: 82.4,
            2011: 79.8,
            2012: 81.1,
            2013: 78.7,
            2014: 75.7,
            2015: 72.3,
            2016: 69.3,
            2017: 65.2,
            2018: 61.9,
            2019: 59.6,
            2020: 68.7,
            2021: 69.3,
            2022: 66.1,
            2023: 64.8,
            2024: 63.5,
            2025: 62.5,
        },
        "interest_rate_10y": {
            2010: 2.7,
            2011: 2.6,
            2012: 1.5,
            2013: 1.6,
            2014: 1.2,
            2015: 0.5,
            2016: 0.1,
            2017: 0.3,
            2018: 0.4,
            2019: -0.3,
            2020: -0.5,
            2021: -0.3,
            2022: 1.8,
            2023: 2.5,
            2024: 2.3,
            2025: 2.2,
        },
    },
    "ES": {
        "gdp_growth": {
            2010: 0.2,
            2011: -0.8,
            2012: -3.0,
            2013: -1.4,
            2014: 1.4,
            2015: 3.8,
            2016: 3.0,
            2017: 3.0,
            2018: 2.3,
            2019: 2.0,
            2020: -11.2,
            2021: 5.5,
            2022: 5.8,
            2023: 2.5,
            2024: 2.1,
            2025: 1.9,
        },
        "unemployment": {
            2010: 19.9,
            2011: 21.4,
            2012: 24.8,
            2013: 26.1,
            2014: 24.4,
            2015: 22.1,
            2016: 19.6,
            2017: 17.2,
            2018: 15.3,
            2019: 14.1,
            2020: 15.5,
            2021: 14.8,
            2022: 12.9,
            2023: 12.1,
            2024: 11.5,
            2025: 11.0,
        },
        "inflation": {
            2010: 2.0,
            2011: 3.1,
            2012: 2.4,
            2013: 1.5,
            2014: -0.2,
            2015: -0.6,
            2016: -0.3,
            2017: 2.0,
            2018: 1.7,
            2019: 0.8,
            2020: -0.3,
            2021: 3.0,
            2022: 8.3,
            2023: 3.4,
            2024: 2.9,
            2025: 2.3,
        },
        "debt_to_gdp": {
            2010: 60.5,
            2011: 69.9,
            2012: 86.3,
            2013: 95.8,
            2014: 100.7,
            2015: 99.3,
            2016: 99.2,
            2017: 98.6,
            2018: 97.5,
            2019: 95.5,
            2020: 120.3,
            2021: 118.3,
            2022: 113.2,
            2023: 107.7,
            2024: 105.0,
            2025: 103.0,
        },
        "interest_rate_10y": {
            2010: 4.3,
            2011: 5.4,
            2012: 5.8,
            2013: 4.6,
            2014: 2.7,
            2015: 1.7,
            2016: 1.4,
            2017: 1.6,
            2018: 1.4,
            2019: 0.7,
            2020: 0.4,
            2021: 0.3,
            2022: 2.8,
            2023: 3.5,
            2024: 3.3,
            2025: 3.1,
        },
    },
    "FR": {
        "gdp_growth": {
            2010: 1.9,
            2011: 2.2,
            2012: 0.3,
            2013: 0.6,
            2014: 1.0,
            2015: 1.1,
            2016: 1.1,
            2017: 2.4,
            2018: 1.8,
            2019: 1.8,
            2020: -7.7,
            2021: 6.4,
            2022: 2.5,
            2023: 0.9,
            2024: 0.7,
            2025: 1.1,
        },
        "unemployment": {
            2010: 9.3,
            2011: 9.2,
            2012: 9.8,
            2013: 10.3,
            2014: 10.3,
            2015: 10.4,
            2016: 10.1,
            2017: 9.4,
            2018: 9.1,
            2019: 8.4,
            2020: 8.0,
            2021: 7.9,
            2022: 7.3,
            2023: 7.3,
            2024: 7.5,
            2025: 7.6,
        },
        "inflation": {
            2010: 1.7,
            2011: 2.3,
            2012: 2.2,
            2013: 1.0,
            2014: 0.6,
            2015: 0.1,
            2016: 0.3,
            2017: 1.2,
            2018: 2.1,
            2019: 1.3,
            2020: 0.5,
            2021: 2.1,
            2022: 5.9,
            2023: 5.2,
            2024: 2.3,
            2025: 1.9,
        },
        "debt_to_gdp": {
            2010: 85.3,
            2011: 87.8,
            2012: 90.6,
            2013: 93.4,
            2014: 94.9,
            2015: 95.6,
            2016: 98.0,
            2017: 98.3,
            2018: 97.8,
            2019: 97.4,
            2020: 114.6,
            2021: 112.9,
            2022: 111.6,
            2023: 110.6,
            2024: 112.0,
            2025: 113.5,
        },
        "interest_rate_10y": {
            2010: 3.1,
            2011: 3.3,
            2012: 2.5,
            2013: 2.2,
            2014: 1.7,
            2015: 0.8,
            2016: 0.5,
            2017: 0.8,
            2018: 0.8,
            2019: 0.1,
            2020: -0.2,
            2021: 0.0,
            2022: 2.3,
            2023: 3.0,
            2024: 2.9,
            2025: 2.7,
        },
    },
    "IT": {
        "gdp_growth": {
            2010: 1.7,
            2011: 0.7,
            2012: -3.0,
            2013: -1.8,
            2014: 0.0,
            2015: 0.8,
            2016: 1.3,
            2017: 1.7,
            2018: 0.9,
            2019: 0.5,
            2020: -9.0,
            2021: 7.0,
            2022: 3.7,
            2023: 0.7,
            2024: 0.7,
            2025: 0.9,
        },
        "unemployment": {
            2010: 8.4,
            2011: 8.4,
            2012: 10.7,
            2013: 12.1,
            2014: 12.7,
            2015: 11.9,
            2016: 11.7,
            2017: 11.2,
            2018: 10.6,
            2019: 10.0,
            2020: 9.3,
            2021: 9.5,
            2022: 8.1,
            2023: 7.6,
            2024: 7.0,
            2025: 6.8,
        },
        "inflation": {
            2010: 1.6,
            2011: 2.9,
            2012: 3.3,
            2013: 1.2,
            2014: 0.2,
            2015: 0.1,
            2016: -0.1,
            2017: 1.3,
            2018: 1.2,
            2019: 0.6,
            2020: -0.1,
            2021: 1.9,
            2022: 8.7,
            2023: 5.9,
            2024: 2.0,
            2025: 1.8,
        },
        "debt_to_gdp": {
            2010: 119.2,
            2011: 119.7,
            2012: 126.5,
            2013: 132.5,
            2014: 135.4,
            2015: 135.3,
            2016: 134.8,
            2017: 134.2,
            2018: 134.4,
            2019: 134.1,
            2020: 154.9,
            2021: 149.8,
            2022: 144.4,
            2023: 140.6,
            2024: 138.0,
            2025: 136.5,
        },
        "interest_rate_10y": {
            2010: 4.0,
            2011: 5.4,
            2012: 5.5,
            2013: 4.3,
            2014: 2.9,
            2015: 1.7,
            2016: 1.5,
            2017: 2.1,
            2018: 2.6,
            2019: 1.4,
            2020: 1.2,
            2021: 0.8,
            2022: 3.2,
            2023: 4.0,
            2024: 3.7,
            2025: 3.5,
        },
    },
    "EU_AVG": {
        "gdp_growth": {
            2010: 2.2,
            2011: 1.8,
            2012: -0.7,
            2013: 0.0,
            2014: 1.6,
            2015: 2.3,
            2016: 2.0,
            2017: 2.8,
            2018: 2.1,
            2019: 1.8,
            2020: -5.7,
            2021: 5.4,
            2022: 3.4,
            2023: 0.5,
            2024: 0.9,
            2025: 1.4,
        },
        "unemployment": {
            2010: 9.6,
            2011: 9.7,
            2012: 10.5,
            2013: 10.9,
            2014: 10.2,
            2015: 9.4,
            2016: 8.6,
            2017: 7.6,
            2018: 6.8,
            2019: 6.3,
            2020: 7.1,
            2021: 7.0,
            2022: 6.2,
            2023: 6.0,
            2024: 6.1,
            2025: 6.0,
        },
        "inflation": {
            2010: 2.1,
            2011: 3.1,
            2012: 2.6,
            2013: 1.3,
            2014: 0.6,
            2015: 0.1,
            2016: 0.2,
            2017: 1.7,
            2018: 1.9,
            2019: 1.4,
            2020: 0.7,
            2021: 2.9,
            2022: 9.2,
            2023: 6.4,
            2024: 2.6,
            2025: 2.1,
        },
        "debt_to_gdp": {
            2010: 79.0,
            2011: 81.5,
            2012: 84.8,
            2013: 86.2,
            2014: 86.7,
            2015: 84.9,
            2016: 83.8,
            2017: 81.7,
            2018: 79.7,
            2019: 77.5,
            2020: 90.0,
            2021: 88.0,
            2022: 84.0,
            2023: 82.6,
            2024: 82.0,
            2025: 81.5,
        },
        "interest_rate_10y": {
            2010: 3.5,
            2011: 4.1,
            2012: 3.6,
            2013: 3.0,
            2014: 2.2,
            2015: 1.3,
            2016: 0.9,
            2017: 1.1,
            2018: 1.2,
            2019: 0.4,
            2020: 0.2,
            2021: 0.2,
            2022: 2.5,
            2023: 3.1,
            2024: 2.9,
            2025: 2.7,
        },
    },
    "EA_AVG": {
        "gdp_growth": {
            2010: 2.1,
            2011: 1.6,
            2012: -0.9,
            2013: -0.2,
            2014: 1.4,
            2015: 2.0,
            2016: 1.9,
            2017: 2.6,
            2018: 1.8,
            2019: 1.6,
            2020: -6.1,
            2021: 5.3,
            2022: 3.3,
            2023: 0.4,
            2024: 0.8,
            2025: 1.3,
        },
        "unemployment": {
            2010: 10.2,
            2011: 10.2,
            2012: 11.4,
            2013: 12.0,
            2014: 11.6,
            2015: 10.9,
            2016: 10.0,
            2017: 9.1,
            2018: 8.2,
            2019: 7.6,
            2020: 8.0,
            2021: 7.7,
            2022: 6.7,
            2023: 6.5,
            2024: 6.5,
            2025: 6.4,
        },
        "inflation": {
            2010: 1.6,
            2011: 2.7,
            2012: 2.5,
            2013: 1.4,
            2014: 0.4,
            2015: 0.2,
            2016: 0.2,
            2017: 1.5,
            2018: 1.8,
            2019: 1.2,
            2020: 0.3,
            2021: 2.6,
            2022: 8.4,
            2023: 5.4,
            2024: 2.4,
            2025: 2.0,
        },
        "debt_to_gdp": {
            2010: 84.6,
            2011: 87.3,
            2012: 91.8,
            2013: 93.4,
            2014: 93.2,
            2015: 91.0,
            2016: 89.8,
            2017: 87.7,
            2018: 85.8,
            2019: 83.8,
            2020: 97.2,
            2021: 95.4,
            2022: 91.4,
            2023: 89.9,
            2024: 89.0,
            2025: 88.5,
        },
        "interest_rate_10y": {
            2010: 3.6,
            2011: 4.3,
            2012: 3.8,
            2013: 3.1,
            2014: 2.3,
            2015: 1.3,
            2016: 1.0,
            2017: 1.2,
            2018: 1.3,
            2019: 0.4,
            2020: 0.3,
            2021: 0.2,
            2022: 2.6,
            2023: 3.2,
            2024: 3.0,
            2025: 2.8,
        },
    },
}

INDICATORS = ["gdp_growth", "unemployment", "inflation", "debt_to_gdp", "interest_rate_10y"]

INDICATOR_NOISE = {
    "gdp_growth": 0.15,
    "unemployment": 0.10,
    "inflation": 0.10,
    "debt_to_gdp": 0.3,
    "interest_rate_10y": 0.05,
}


# =============================================================================
# Data generation functions
# =============================================================================


def _interpolate_and_noise(
    ref_points: Dict[int, float],
    years: List[int],
    noise_scale: float,
) -> np.ndarray:
    """Interpolate reference points across years and add controlled noise.

    Parameters
    ----------
    ref_points : dict[int, float]
        Mapping of year to reference value.
    years : list[int]
        Full list of years to generate data for.
    noise_scale : float
        Standard deviation of Gaussian noise to add.

    Returns
    -------
    np.ndarray
        Interpolated values with noise for each year.
    """
    ref_years = sorted(ref_points.keys())
    ref_values = [ref_points[y] for y in ref_years]

    interpolated = np.interp(years, ref_years, ref_values)
    noise = rng.normal(0, noise_scale, size=len(years))
    return np.round(interpolated + noise, 2)


def generate_benchmark_data() -> pd.DataFrame:
    """Generate the full EU benchmark dataset.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: date_key, country_code, country_name,
        indicator, value.
    """
    log_section(logger, "Generating EU Benchmark Data")

    rows = []
    for country_code, country_name in COUNTRIES.items():
        logger.info(f"Generating data for {country_name} ({country_code})")
        for indicator in INDICATORS:
            ref_points = REFERENCE_DATA[country_code][indicator]
            noise_scale = INDICATOR_NOISE[indicator]
            values = _interpolate_and_noise(ref_points, YEARS, noise_scale)

            for year, value in zip(YEARS, values):
                rows.append(
                    {
                        "date_key": str(year),
                        "country_code": country_code,
                        "country_name": country_name,
                        "indicator": indicator,
                        "value": value,
                    }
                )

    df = pd.DataFrame(rows)
    df["source"] = "Eurostat/ECB (synthetic benchmark)"
    logger.info(
        f"Generated {len(df):,} benchmark records "
        f"({len(COUNTRIES)} countries x {len(INDICATORS)} indicators x {len(YEARS)} years)"
    )
    return df


def save_to_csv(df: pd.DataFrame) -> Path:
    """Save the benchmark DataFrame to CSV with metadata.

    Parameters
    ----------
    df : pd.DataFrame
        The benchmark data.

    Returns
    -------
    Path
        Path to the saved CSV file.
    """
    import hashlib
    import json
    from datetime import datetime, timezone

    output_path = RAW_DATA_DIR / "raw_eu_benchmark.csv"
    df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info(f"Saved CSV: {output_path}")

    # Write meta.json with correct row count
    cs = hashlib.sha256(output_path.read_bytes()).hexdigest()
    meta = {
        "filename": output_path.name,
        "rows": len(df),
        "columns": list(df.columns),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sha256": cs,
    }
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return output_path


def create_benchmark_table(db_path: Path) -> None:
    """Execute the DDL script to create the benchmark table.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.
    """
    ddl_path = DDL_DIR / "create_benchmark_tables.sql"
    with open(ddl_path, "r", encoding="utf-8") as f:
        ddl_sql = f.read()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(ddl_sql)
        conn.commit()
        logger.info(f"Created benchmark table in {db_path.name}")
    finally:
        conn.close()


def load_to_database(df: pd.DataFrame, db_path: Path) -> int:
    """Load the benchmark DataFrame into the SQLite database.

    Parameters
    ----------
    df : pd.DataFrame
        The benchmark data.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    int
        Number of rows inserted.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        df.to_sql("fact_eu_benchmark", conn, if_exists="append", index=False)
        row_count = len(df)
        logger.info(f"Loaded {row_count:,} rows into fact_eu_benchmark")
        return row_count
    finally:
        conn.close()


# =============================================================================
# Main pipeline
# =============================================================================


def run_pipeline() -> None:
    """Execute the full EU benchmark data generation pipeline."""
    log_section(logger, "EU Benchmark Data Generation Pipeline")

    # Ensure directories exist
    ensure_directories()

    # Generate data
    df = generate_benchmark_data()

    # Save CSV
    save_to_csv(df)

    # Create table and load into database
    create_benchmark_table(DATABASE_PATH)
    load_to_database(df, DATABASE_PATH)

    log_section(logger, "Pipeline Complete")
    logger.info(f"Database: {DATABASE_PATH}")
    logger.info(f"CSV:      {RAW_DATA_DIR / 'raw_eu_benchmark.csv'}")


if __name__ == "__main__":
    run_pipeline()
