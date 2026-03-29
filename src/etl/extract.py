"""
Portugal Data Intelligence - ETL: Extract Module
==================================================
Reads raw CSV files from data/raw/ and returns pandas DataFrames
for each data pillar.

Usage:
    from src.etl.extract import extract_all
    raw_data = extract_all()
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config.settings import DATA_PILLARS, RAW_DATA_DIR
from src.etl.lineage import file_checksum
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)

# Minimum required columns per pillar (pre-rename, as they appear in raw CSV).
# These are the columns the transform phase needs — anything missing here
# would cause a late, confusing failure during transformation.
_REQUIRED_COLUMNS: Dict[str, List[str]] = {
    "gdp": [
        "date",
        "year",
        "quarter",
        "nominal_gdp_eur_millions",
        "real_gdp_eur_millions",
        "gdp_growth_rate_yoy",
        "gdp_per_capita_eur",
    ],
    "unemployment": [
        "date",
        "unemployment_rate",
        "youth_unemployment_rate",
        "long_term_unemployment_rate",
        "labour_force_participation_rate",
    ],
    "credit": [
        "date",
        "total_credit_eur_millions",
        "nfc_credit_eur_millions",
        "household_credit_eur_millions",
        "npl_ratio",
    ],
    "interest_rates": [
        "date",
        "ecb_main_refinancing_rate",
        "euribor_3m",
        "euribor_6m",
        "euribor_12m",
        "portugal_10y_bond_yield",
    ],
    "inflation": [
        "date",
        "hicp_annual_rate",
        "cpi_annual_rate",
        "core_inflation_rate",
    ],
    "public_debt": [
        "date",
        "year",
        "quarter",
        "total_debt_eur_millions",
        "debt_to_gdp_ratio",
        "budget_balance_pct_gdp",
    ],
}

# Maps each pillar key to the expected CSV filename in data/raw/.
_RAW_FILES: Dict[str, str] = {
    "gdp": "raw_gdp.csv",
    "unemployment": "raw_unemployment.csv",
    "credit": "raw_credit.csv",
    "interest_rates": "raw_interest_rates.csv",
    "inflation": "raw_inflation.csv",
    "public_debt": "raw_public_debt.csv",
}


def _validate_file(file_path: Path) -> bool:
    """Return True if *file_path* exists and is non-empty."""
    if not file_path.exists():
        logger.error("File not found: %s", file_path)
        return False
    if file_path.stat().st_size == 0:
        logger.error("File is empty: %s", file_path)
        return False
    return True


def extract_pillar(pillar_key: str) -> Optional[pd.DataFrame]:
    """Extract a single pillar from its raw CSV file.

    Parameters
    ----------
    pillar_key : str
        One of the keys from DATA_PILLARS (e.g. ``'gdp'``).

    Returns
    -------
    pd.DataFrame or None
        The loaded DataFrame, or ``None`` if the file is missing / unreadable.
    """
    filename = _RAW_FILES.get(pillar_key)
    if filename is None:
        logger.error("No raw file mapping for pillar '%s'", pillar_key)
        return None

    file_path = RAW_DATA_DIR / filename

    if not _validate_file(file_path):
        return None

    # Verify checksum if sidecar exists.
    sha_path = file_path.with_suffix(file_path.suffix + ".sha256")
    if sha_path.exists():
        expected = sha_path.read_text(encoding="utf-8").strip()
        actual = file_checksum(file_path)
        if actual and actual != expected:
            logger.warning(
                "Checksum mismatch for %s (expected %s..., got %s...)",
                file_path.name,
                expected[:12],
                actual[:12],
            )
        else:
            logger.debug("Checksum OK for %s", file_path.name)

    try:
        df = pd.read_csv(file_path, encoding="utf-8")
        logger.info(
            "  Extracted '%s' from %s: %s rows x %d columns",
            pillar_key,
            filename,
            f"{len(df):,}",
            len(df.columns),
        )

        # Validate schema: check that all required columns are present
        required = _REQUIRED_COLUMNS.get(pillar_key)
        if required is not None:
            missing = [c for c in required if c not in df.columns]
            if missing:
                logger.error(
                    "  [%s] CSV schema validation failed — missing columns: %s",
                    pillar_key,
                    ", ".join(missing),
                )
                return None

        return df
    except pd.errors.ParserError as exc:
        logger.error("CSV parse error for %s: %s", file_path, exc)
        return None
    except Exception as exc:
        logger.error("Failed to read %s: %s", file_path, exc)
        return None


def extract_all() -> Dict[str, pd.DataFrame]:
    """Extract raw data for every pillar defined in ``DATA_PILLARS``.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keyed by pillar name. Pillars whose files are missing or
        unreadable are omitted.
    """
    log_section(logger, "EXTRACT PHASE")
    logger.info("Raw data directory: %s", RAW_DATA_DIR)

    results: Dict[str, pd.DataFrame] = {}

    for pillar_key in DATA_PILLARS:
        df = extract_pillar(pillar_key)
        if df is not None:
            results[pillar_key] = df

    extracted = len(results)
    total = len(DATA_PILLARS)
    logger.info("Extraction complete: %d/%d pillars loaded", extracted, total)

    if extracted < total:
        missing = sorted(set(DATA_PILLARS.keys()) - set(results.keys()))
        logger.warning("Missing pillars: %s", ", ".join(missing))

    return results
