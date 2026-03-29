"""
Portugal Data Intelligence - ETL: Transform Module
====================================================
Cleans, validates, and transforms raw DataFrames produced by the
extract module and writes processed CSV files to data/processed/.

Each pillar is driven by a declarative config dict:
  rename      → column rename mapping
  date_key    → "quarterly" or "monthly"
  clip_rules  → [(column, lower, upper), ...]
  round_dp    → decimal places
  keep_cols   → ordered list of output columns
  post_hook   → optional callable(df) -> df

Usage:
    from src.etl.transform import transform_all
    processed = transform_all(raw_data)
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import DATA_PILLARS, PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)


# ============================================================================
# Column rename mappings (raw CSV → schema)
# ============================================================================

_GDP_RENAME = {
    "nominal_gdp_eur_millions": "nominal_gdp",
    "real_gdp_eur_millions": "real_gdp",
    "gdp_growth_rate_yoy": "gdp_growth_yoy",
    "gdp_growth_rate_qoq": "gdp_growth_qoq",
    "gdp_per_capita_eur": "gdp_per_capita",
}

_CREDIT_RENAME = {
    "total_credit_eur_millions": "total_credit",
    "nfc_credit_eur_millions": "credit_nfc",
    "household_credit_eur_millions": "credit_households",
}

_INFLATION_RENAME = {
    "hicp_annual_rate": "hicp",
    "cpi_annual_rate": "cpi_estimated",
    "core_inflation_rate": "core_inflation",
}

_PUBLIC_DEBT_RENAME = {
    "total_debt_eur_millions": "total_debt",
    "budget_balance_pct_gdp": "budget_deficit",
}


# ============================================================================
# Post-hooks (pillar-specific logic that doesn't fit the generic pattern)
# ============================================================================


def _inflation_post_hook(df: pd.DataFrame) -> pd.DataFrame:
    """Mark CPI as estimated when identical to HICP.

    The Eurostat API returns the same series for both HICP and CPI.
    The Portuguese CPI (INE) typically tracks 0.1-0.3 pp below HICP
    due to different basket weights.  When values are identical we
    apply a small realistic offset and log a warning that the column
    is estimated, not sourced from INE.
    """
    if "hicp" not in df.columns or "cpi_estimated" not in df.columns:
        return df

    diff = (df["hicp"] - df["cpi_estimated"]).abs()
    pct_identical = (diff < 0.01).sum() / len(df)
    if pct_identical > 0.95:  # >95% of rows are identical
        rng = np.random.default_rng(42)
        offset = rng.normal(-0.15, 0.08, len(df))
        df["cpi_estimated"] = (df["hicp"] + offset).round(2)
        logger.warning(
            "  [inflation] CPI was identical to HICP — column 'cpi_estimated' "
            "contains estimated values (offset from HICP), not real INE CPI data"
        )
    return df


def _public_debt_post_hook(df: pd.DataFrame) -> pd.DataFrame:
    """Fix public debt data quality issues.

    1. Clip budget_deficit to plausible range [-15%, +5%]
    2. Populate external_debt_share_estimated if all null (estimate ~48% average)
    3. Extrapolate missing final quarter if needed
    4. Add annualised budget deficit (rolling 4-quarter average)
    """
    # 1. Clip extreme budget deficit values
    #    Portugal's worst deficit was ~-11.4% (2010); [-15%, +5%] is generous.
    if "budget_deficit" in df.columns:
        extreme = (df["budget_deficit"] < -15) | (df["budget_deficit"] > 5)
        n_extreme = int(extreme.sum())
        if n_extreme > 0:
            df["budget_deficit"] = df["budget_deficit"].clip(lower=-15, upper=5)
            logger.info(
                "  [public_debt] Clipped %d extreme budget_deficit values to [-15%%, +5%%]",
                n_extreme,
            )

    # 2. Rename external_debt_share -> external_debt_share_estimated (column kept
    #    as "_estimated" because annual Eurostat data is interpolated to quarters).
    if "external_debt_share" in df.columns:
        df = df.rename(columns={"external_debt_share": "external_debt_share_estimated"})
    if "external_debt_share_estimated" in df.columns:
        n_real = df["external_debt_share_estimated"].notna().sum()
        if n_real > 0:
            # Real data available from Eurostat gov_10dd_ggd — forward-fill
            # missing trailing quarters (e.g. 2025 not yet published).
            df["external_debt_share_estimated"] = (
                df["external_debt_share_estimated"].interpolate(method="linear").ffill()
            )
            n_filled = df["external_debt_share_estimated"].notna().sum()
            logger.info(
                "  [public_debt] external_debt_share_estimated: %d/%d values from "
                "Eurostat (gov_10dd_ggd), %d forward-filled",
                n_real,
                len(df),
                n_filled - n_real,
            )
        else:
            # Completely missing — fall back to synthetic estimates
            rng_debt = np.random.default_rng(43)
            n = len(df)
            base = np.linspace(48.0, 46.0, n)  # slight downward trend
            noise = rng_debt.normal(0, 0.3, n)
            df["external_debt_share_estimated"] = np.round(np.clip(base + noise, 40, 58), 1)
            logger.warning(
                "  [public_debt] external_debt_share_estimated populated with "
                "estimates (~48%%) — not sourced from API"
            )

    # 3. Extrapolate missing final quarter(s) if series is incomplete
    from config.settings import END_YEAR, START_YEAR

    if "date_key" in df.columns:
        expected_quarters = (END_YEAR - START_YEAR + 1) * 4
        if len(df) < expected_quarters:
            # Build full quarterly index
            full_keys = []
            for y in range(START_YEAR, END_YEAR + 1):
                for q in range(1, 5):
                    full_keys.append(f"{y}-Q{q}")
            original_len = len(df)
            df = df.set_index("date_key").reindex(full_keys)
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            # Linear interpolation for interior gaps, then fill edges
            df[numeric_cols] = df[numeric_cols].interpolate(method="linear").ffill().bfill()
            df = df.reset_index().rename(columns={"index": "date_key"})
            n_extrapolated = expected_quarters - original_len
            if n_extrapolated > 1:
                logger.warning(
                    "  [public_debt] Extrapolated %d quarters — values may be unreliable",
                    n_extrapolated,
                )
            else:
                logger.info(
                    "  [public_debt] Extrapolated to %d quarters (was %d)",
                    expected_quarters,
                    original_len,
                )

    # 4. Add annualised budget deficit (rolling 4-quarter average)
    #    Each quarterly budget_deficit is expressed as % of quarterly GDP.
    #    The annual figure ≈ average of the 4 quarterly percentages, not the sum.
    if "budget_deficit" in df.columns:
        df = df.sort_values("date_key").reset_index(drop=True)
        df["budget_deficit_annual"] = df["budget_deficit"].rolling(4, min_periods=4).mean()
        logger.info("  [public_debt] Added budget_deficit_annual (rolling 4-quarter average)")

    return df


def _interest_rates_post_hook(df: pd.DataFrame) -> pd.DataFrame:
    """Forward/backward fill ECB rate nulls.

    The ECB main refinancing rate is a stepped function (changes only on
    policy dates). Nulls at the start/end of the series should be filled
    with the nearest known value.
    """
    col = "ecb_main_refinancing_rate"
    if col not in df.columns:
        return df

    n_nulls = df[col].isna().sum()
    if n_nulls == 0:
        return df

    # The ECB rate was 1.00% from May 2009 to March 2011. The API may not
    # cover this period, so fill known values before using ffill/bfill.
    if "date_key" in df.columns:
        mask = (df["date_key"] >= "2010-01") & (df["date_key"] <= "2011-03") & df[col].isna()
        df.loc[mask, col] = 1.0

    df[col] = df[col].ffill().bfill()
    logger.info("  [interest_rates] Filled %d null ECB rate values (ffill+bfill)", n_nulls)
    return df


def _credit_post_hook(df: pd.DataFrame) -> pd.DataFrame:
    """Interpolate missing months and enforce credit component invariants.

    1. The BdP credit series transitions from quarterly to monthly around
       2011.  This hook fills gaps by creating a complete monthly index and
       linearly interpolating numeric columns.
    2. Enforces NFC + Households <= Total Credit (may be violated by
       independent interpolation or noisy synthetic data).
    """
    # --- Interpolation: fix duplicated early months (quarterly→monthly) ---
    if "date_key" in df.columns:
        from config.settings import END_YEAR, START_YEAR

        # Detect and fix duplicated values at the start (quarterly data broadcast)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(df) >= 3:
            first_vals = df[numeric_cols].head(3)
            if first_vals.nunique().max() <= 1 and len(first_vals) == 3:
                # First 3 months are identical — replace with NaN and interpolate
                df.loc[df.index[:2], numeric_cols] = np.nan
                df[numeric_cols] = df[numeric_cols].interpolate(method="linear").bfill()
                logger.info("  [credit] Fixed duplicated first months via interpolation")

        # Fill missing months if any
        full_range = pd.date_range(
            start=f"{START_YEAR}-01-01",
            end=f"{END_YEAR}-12-01",
            freq="MS",
        )
        full_keys = full_range.strftime("%Y-%m")

        missing_count = len(full_keys) - len(df)
        if missing_count > 0:
            df = df.set_index("date_key").reindex(full_keys)
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].interpolate(method="linear").bfill()
            df = df.reset_index().rename(columns={"index": "date_key"})
            logger.info(
                "  [credit] Interpolated %d missing months (quarterly→monthly)",
                missing_count,
            )

    # --- Enforce invariant: NFC + Households <= Total Credit ---
    if all(c in df.columns for c in ("total_credit", "credit_nfc", "credit_households")):
        parts = df["credit_nfc"] + df["credit_households"]
        violations = parts > df["total_credit"]
        n_violations = int(violations.sum())
        if n_violations > 0:
            ratio = df.loc[violations, "total_credit"] / parts[violations]
            df.loc[violations, "credit_nfc"] = (df.loc[violations, "credit_nfc"] * ratio).round(2)
            df.loc[violations, "credit_households"] = (
                df.loc[violations, "credit_households"] * ratio
            ).round(2)
            logger.info(
                "  [credit] Scaled %d rows where NFC + Households exceeded Total",
                n_violations,
            )

    return df


def _gdp_post_hook(df: pd.DataFrame) -> pd.DataFrame:
    """Always recalculate YoY and QoQ growth from real_gdp.

    The raw API values may reflect nominal rather than real growth.
    Deriving from real_gdp ensures consistency.
    """
    if "real_gdp" not in df.columns:
        return df

    df = df.sort_values("date_key").reset_index(drop=True)

    # QoQ: compare to previous quarter
    df["gdp_growth_qoq"] = df["real_gdp"].pct_change() * 100

    # YoY: compare to same quarter previous year (shift 4 quarters)
    prev_year = df["real_gdp"].shift(4)
    df["gdp_growth_yoy"] = ((df["real_gdp"] / prev_year) - 1) * 100

    logger.info("  [gdp] Recalculated YoY and QoQ growth rates from real_gdp")
    return df


# ============================================================================
# Pillar configuration (single source of truth)
# ============================================================================

_PILLAR_CONFIGS: Dict[str, Dict[str, Any]] = {
    "gdp": {
        "rename": _GDP_RENAME,
        "date_key": "quarterly",
        "clip_rules": [
            ("nominal_gdp", 0, None),
            ("real_gdp", 0, None),
            ("gdp_per_capita", 0, None),
        ],
        "round_dp": 2,
        "keep_cols": [
            "date_key",
            "nominal_gdp",
            "real_gdp",
            "gdp_growth_yoy",
            "gdp_growth_qoq",
            "gdp_per_capita",
        ],
        "post_hook": _gdp_post_hook,
    },
    "unemployment": {
        "rename": {},
        "date_key": "monthly",
        "clip_rules": [
            ("unemployment_rate", 0, 100),
            ("youth_unemployment_rate", 0, 100),
            ("long_term_unemployment_rate", 0, 100),
            ("labour_force_participation_rate", 0, 100),
        ],
        "round_dp": 1,
        "keep_cols": [
            "date_key",
            "unemployment_rate",
            "youth_unemployment_rate",
            "long_term_unemployment_rate",
            "labour_force_participation_rate",
        ],
    },
    "credit": {
        "rename": _CREDIT_RENAME,
        "date_key": "monthly",
        "clip_rules": [
            ("total_credit", 0, None),
            ("credit_nfc", 0, None),
            ("credit_households", 0, None),
            ("npl_ratio", 0, 100),
        ],
        "round_dp": 2,
        "keep_cols": [
            "date_key",
            "total_credit",
            "credit_nfc",
            "credit_households",
            "npl_ratio",
        ],
        "post_hook": _credit_post_hook,
    },
    "interest_rates": {
        "rename": {},
        "date_key": "monthly",
        "clip_rules": [
            ("ecb_main_refinancing_rate", -2, 20),
            ("euribor_3m", -2, 20),
            ("euribor_6m", -2, 20),
            ("euribor_12m", -2, 20),
            ("portugal_10y_bond_yield", -2, 20),
        ],
        "round_dp": 3,
        "keep_cols": [
            "date_key",
            "ecb_main_refinancing_rate",
            "euribor_3m",
            "euribor_6m",
            "euribor_12m",
            "portugal_10y_bond_yield",
        ],
        "post_hook": _interest_rates_post_hook,
    },
    "inflation": {
        "rename": _INFLATION_RENAME,
        "date_key": "monthly",
        "clip_rules": [
            ("hicp", -5, 30),
            ("cpi_estimated", -5, 30),
            ("core_inflation", -5, 30),
        ],
        "round_dp": 2,
        "keep_cols": ["date_key", "hicp", "cpi_estimated", "core_inflation"],
        "post_hook": _inflation_post_hook,
    },
    "public_debt": {
        "rename": _PUBLIC_DEBT_RENAME,
        "date_key": "quarterly",
        "clip_rules": [
            ("total_debt", 0, None),
            ("debt_to_gdp_ratio", 0, 300),
            ("external_debt_share_estimated", 0, 100),
        ],
        "round_dp": 2,
        "keep_cols": [
            "date_key",
            "total_debt",
            "debt_to_gdp_ratio",
            "budget_deficit",
            "budget_deficit_annual",
            "external_debt_share_estimated",
        ],
        "post_hook": _public_debt_post_hook,
    },
}


# ============================================================================
# Helpers
# ============================================================================


def _derive_date_key_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Create ``date_key`` in ``YYYY-MM`` format from the raw ``date`` column."""
    if "date" in df.columns:
        df["date_key"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m")
    return df


def _derive_date_key_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    """Create ``date_key`` in ``YYYY-QN`` format."""
    if "year" in df.columns and "quarter" in df.columns:
        df["date_key"] = df["year"].astype(str) + "-Q" + df["quarter"].astype(str)
    elif "date" in df.columns:
        dt = pd.to_datetime(df["date"])
        df["date_key"] = dt.dt.year.astype(str) + "-Q" + dt.dt.quarter.astype(str)
    return df


_DATE_KEY_DERIVERS = {
    "monthly": _derive_date_key_monthly,
    "quarterly": _derive_date_key_quarterly,
}


def _get_fetch_date(pillar_key: str) -> Optional[datetime]:
    """Read the fetch timestamp from the raw CSV meta.json file."""
    import json

    meta_path = RAW_DATA_DIR / f"raw_{pillar_key}.csv.meta.json"
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return datetime.fromisoformat(meta["fetched_at"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def _add_provisional_flag(
    df: pd.DataFrame,
    pillar_key: str,
    date_key_type: str,
) -> pd.DataFrame:
    """Add ``is_provisional`` column based on the fetch date.

    Data points whose date_key falls after the last confirmed period are
    marked as provisional (True), meaning they are preliminary estimates
    or projections rather than confirmed final observations.

    Publication lags (aligned with Eurostat release calendar):
      - Quarterly (GDP, debt): ~6 months after quarter end (flash ~45d, revised ~90d, final ~120-150d)
      - Monthly (unemployment, credit, rates, inflation): ~2 months
    """
    fetch_dt = _get_fetch_date(pillar_key)
    if fetch_dt is None or "date_key" not in df.columns:
        df["is_provisional"] = False
        return df

    if date_key_type == "quarterly":
        # Quarterly data: use 6-month lag from fetch date.
        # E.g., fetched 2026-03-26 → go back 6 months → Sep 2025 → Q3 2025
        # Q3 2025 is the last confirmed quarter; Q4 2025 is provisional.
        fetch_year = fetch_dt.year
        fetch_month = fetch_dt.month
        ref_month = fetch_month - 6
        ref_year = fetch_year
        if ref_month <= 0:
            ref_month += 12
            ref_year -= 1
        last_confirmed_q = (ref_month - 1) // 3 + 1
        last_confirmed_key = f"{ref_year}-Q{last_confirmed_q}"
        df["is_provisional"] = df["date_key"] > last_confirmed_key
    else:
        # Monthly data: use 4-month lag from fetch date.
        # E.g., fetched 2026-03-26 → go back 4 months → Nov 2025
        # Nov 2025 is the last confirmed month; Dec 2025 is provisional.
        ref_month = fetch_dt.month - 4
        ref_year = fetch_dt.year
        if ref_month <= 0:
            ref_month += 12
            ref_year -= 1
        last_confirmed_key = f"{ref_year}-{ref_month:02d}"
        df["is_provisional"] = df["date_key"] > last_confirmed_key

    n_provisional = int(df["is_provisional"].sum())
    if n_provisional > 0:
        logger.info(
            "  [%s] Marked %d rows as provisional (after fetch date)",
            pillar_key,
            n_provisional,
        )
    return df


def _clip_and_warn(
    df: pd.DataFrame,
    column: str,
    lower: Optional[float],
    upper: Optional[float],
    pillar: str,
) -> pd.DataFrame:
    """Clip values outside the valid range and log outlier counts."""
    if column not in df.columns:
        return df

    series = df[column]
    outliers = pd.Series(False, index=df.index)
    if lower is not None:
        outliers |= series < lower
    if upper is not None:
        outliers |= series > upper

    n_outliers = int(outliers.sum())
    if n_outliers > 0:
        logger.warning(
            "  [%s] %d outlier(s) in '%s' clipped to [%s, %s]",
            pillar,
            n_outliers,
            column,
            lower,
            upper,
        )
        df[column] = series.clip(lower=lower, upper=upper)

    return df


def _log_quality_report(pillar: str, df: pd.DataFrame) -> None:
    """Log a brief data-quality summary."""
    rows, cols = df.shape
    total_nulls = int(df.isna().sum().sum())
    null_pct = (total_nulls / (rows * cols)) * 100 if rows * cols > 0 else 0.0
    logger.info(
        "  [%s] Rows: %s | Columns: %d | Nulls: %s (%.1f%%)",
        pillar,
        f"{rows:,}",
        cols,
        f"{total_nulls:,}",
        null_pct,
    )


def _save_processed(pillar: str, df: pd.DataFrame) -> None:
    """Save a processed DataFrame to ``data/processed/`` as CSV."""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DATA_DIR / f"{pillar}.csv"
    df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("  [%s] Saved to %s", pillar, output_path)


# ============================================================================
# Generic transformer
# ============================================================================


def _transform_pillar(
    pillar_key: str,
    df: pd.DataFrame,
    config: Dict[str, Any],
) -> pd.DataFrame:
    """Apply the standard transformation pipeline driven by *config*.

    Steps: rename → date_key → clip → post_hook → provisional_flag → round → select columns.
    """
    logger.info("  Transforming %s data...", pillar_key)
    df = df.copy()

    # 1. Rename
    rename_map = config.get("rename", {})
    if rename_map:
        df = df.rename(columns=rename_map)

    # 2. Derive date_key
    derive_fn = _DATE_KEY_DERIVERS[config["date_key"]]
    df = derive_fn(df)

    if "date_key" not in df.columns:
        raise ValueError(
            f"[{pillar_key}] Could not derive date_key — "
            f"check raw data has 'date', 'year'+'quarter' columns"
        )

    # 3. Clip
    for col, lo, hi in config.get("clip_rules", []):
        df = _clip_and_warn(df, col, lower=lo, upper=hi, pillar=pillar_key)

    # 4. Post-hook
    post_hook: Optional[Callable] = config.get("post_hook")
    if post_hook is not None:
        df = post_hook(df)

    # 5. Add provisional flag
    df = _add_provisional_flag(df, pillar_key, config["date_key"])

    # 6. Round
    round_dp = config.get("round_dp", 2)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].round(round_dp)

    # 7. Select output columns (warn about missing ones)
    keep_cols = config["keep_cols"] + ["is_provisional"]
    missing_cols = [c for c in keep_cols if c not in df.columns]
    if missing_cols:
        logger.warning(
            "  [%s] Expected columns not found: %s",
            pillar_key,
            ", ".join(missing_cols),
        )
    df = df[[c for c in keep_cols if c in df.columns]]

    _log_quality_report(pillar_key, df)
    return df


def transform_all(raw_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Transform and save all extracted pillar DataFrames.

    Parameters
    ----------
    raw_data : dict[str, pd.DataFrame]
        Raw DataFrames keyed by pillar name.

    Returns
    -------
    dict[str, pd.DataFrame]
        Cleaned DataFrames keyed by pillar name.
    """
    log_section(logger, "TRANSFORM PHASE")
    results: Dict[str, pd.DataFrame] = {}

    for pillar_key, df in raw_data.items():
        config = _PILLAR_CONFIGS.get(pillar_key)
        if config is None:
            logger.warning("No transform config for '%s' — skipping", pillar_key)
            continue

        try:
            transformed = _transform_pillar(pillar_key, df, config)
            _save_processed(pillar_key, transformed)
            results[pillar_key] = transformed
        except Exception as exc:
            logger.error("Transform failed for '%s': %s", pillar_key, exc)

    logger.info(
        "Transformation complete: %d/%d pillars processed",
        len(results),
        len(raw_data),
    )
    return results
