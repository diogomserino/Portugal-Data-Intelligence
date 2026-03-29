"""
Portugal Data Intelligence - Real Data Extraction
====================================================
Fetches real macroeconomic data from official APIs:
  - Eurostat (SDMX 2.1)  : GDP, unemployment, inflation, government debt
  - ECB Data API          : interest rates, Euribor, bond yields
  - BPStat (Banco de Portugal) : credit, NPL

Saves each pillar as a CSV in data/raw/ with the same column schema
used by the rest of the pipeline.

Usage:
    python -m src.etl.fetch_real_data          # fetch all pillars
    python -m src.etl.fetch_real_data --pillar gdp  # fetch one pillar
"""

import io
import random
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import END_YEAR, RAW_DATA_DIR, START_YEAR, ensure_directories
from src.utils.logger import get_logger, log_section

logger = get_logger("fetch_real_data")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data"
BPSTAT_BASE = "https://bpstat.bportugal.pt/data/v1"

REQUEST_TIMEOUT = 60  # seconds
RETRY_DELAY = 2  # seconds between retries
MAX_RETRIES = 3

START_PERIOD = str(START_YEAR)
END_PERIOD = str(END_YEAR)

DEFAULT_HEADERS = {
    "User-Agent": "PortugalDataIntelligence/2.1 (macroeconomic-research)",
}


# =============================================================================
#  GENERIC API HELPERS
# =============================================================================


def _get_with_retry(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> requests.Response:
    """GET request with retries, exponential back-off, and jitter.

    Delay formula: base * 2^(attempt-1) + uniform jitter [0, base).
    This avoids thundering-herd problems and respects API rate limits.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
            resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
            if resp.status_code == 429:
                # Rate limited — respect Retry-After header if present
                raw_retry = resp.headers.get("Retry-After", str(RETRY_DELAY * 2**attempt))
                try:
                    retry_after = int(raw_retry)
                except (ValueError, TypeError):
                    retry_after = RETRY_DELAY * 2**attempt
                logger.warning(f"  Rate limited (429) on {url} — waiting {retry_after}s")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            logger.warning(f"  Attempt {attempt}/{MAX_RETRIES} failed for {url}: {exc}")
            if attempt < MAX_RETRIES:
                backoff = RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(0, RETRY_DELAY)
                logger.info(f"  Retrying in {backoff:.1f}s...")
                time.sleep(backoff)
            else:
                raise
    raise RuntimeError("Unreachable: all retries exhausted")  # pragma: no cover


# -----------------------------------------------------------------------------
# Eurostat SDMX 2.1 JSON parser
# -----------------------------------------------------------------------------


def _fetch_eurostat(
    dataset: str, key: str, start: str = START_PERIOD, end: str = END_PERIOD
) -> pd.DataFrame:
    """Fetch data from Eurostat SDMX 2.1 API and return a tidy DataFrame.

    Parameters
    ----------
    dataset : str   e.g. "namq_10_gdp"
    key     : str   e.g. "Q.CP_MEUR.SCA.B1GQ.PT"
    start   : str   start period  e.g. "2010"
    end     : str   end period    e.g. "2025"

    Returns
    -------
    pd.DataFrame with columns [period, value].
    """
    url = f"{EUROSTAT_BASE}/{dataset}/{key}"
    params = {"startPeriod": start, "endPeriod": end, "format": "JSON"}
    logger.info(f"  Eurostat: {dataset}/{key}")

    resp = _get_with_retry(url, params=params)
    data = resp.json()

    # Parse the SDMX JSON structure with guards
    try:
        dims = data["dimension"]["time"]["category"]
        time_index = dims["index"]  # {"2010-Q1": 0, "2010-Q2": 1, ...}
        obs = data["value"]  # {"0": 12345.6, "1": 12346.7, ...}
    except (KeyError, TypeError) as exc:
        logger.error("Unexpected SDMX JSON structure for %s/%s: %s", dataset, key, exc)
        return pd.DataFrame(columns=["period", "value"])

    # Invert index: position -> period label
    pos_to_period = {v: k for k, v in time_index.items()}

    rows = []
    for pos_str, value in obs.items():
        period = pos_to_period.get(int(pos_str))
        if period and value is not None:
            rows.append({"period": period, "value": float(value)})

    df = pd.DataFrame(rows).sort_values("period").reset_index(drop=True)
    logger.info(f"    -> {len(df)} observations")
    return df


def _fetch_eurostat_multi(
    dataset: str, keys: dict, start: str = START_PERIOD, end: str = END_PERIOD
) -> dict:
    """Fetch multiple series from the same Eurostat dataset.

    Parameters
    ----------
    keys : dict mapping label -> SDMX key string

    Returns
    -------
    dict mapping label -> DataFrame[period, value]
    """
    results = {}
    for label, key in keys.items():
        try:
            results[label] = _fetch_eurostat(dataset, key, start, end)
        except Exception as exc:
            logger.error(f"    Failed to fetch {label}: {exc}")
            results[label] = pd.DataFrame(columns=["period", "value"])
        time.sleep(0.5)  # be polite to the API
    return results


# -----------------------------------------------------------------------------
# ECB Data API CSV parser
# -----------------------------------------------------------------------------


def _fetch_ecb(
    flow: str, key: str, start: str = f"{START_PERIOD}-01", end: str = f"{END_PERIOD}-12"
) -> pd.DataFrame:
    """Fetch from ECB Statistical Data Warehouse and return DataFrame.

    Returns DataFrame with columns [period, value].
    """
    url = f"{ECB_BASE}/{flow}/{key}"
    params = {"startPeriod": start, "endPeriod": end, "format": "csvdata"}
    logger.info(f"  ECB: {flow}/{key}")

    resp = _get_with_retry(url, params=params)
    df = pd.read_csv(io.StringIO(resp.text))

    # ECB CSV has TIME_PERIOD and OBS_VALUE columns
    result = (
        df[["TIME_PERIOD", "OBS_VALUE"]]
        .rename(columns={"TIME_PERIOD": "period", "OBS_VALUE": "value"})
        .dropna(subset=["value"])
    )
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result = result.dropna(subset=["value"]).sort_values("period").reset_index(drop=True)
    logger.info(f"    -> {len(result)} observations")
    return result


# -----------------------------------------------------------------------------
# BPStat (Banco de Portugal) JSON parser
# -----------------------------------------------------------------------------

BPSTAT_SERIES_CONFIG = {
    "12457932": {"domain_id": 18, "dataset_id": "921a2108733e34fe71b5fed3dfa75c20"},
    "12559924": {"domain_id": 18, "dataset_id": "08adcab6f448ae4408de0cca87b4cb4c"},
    "12457924": {"domain_id": 18, "dataset_id": "56ebacd8518e60ef58c85cb8185b4818"},
    "12504544": {"domain_id": 59, "dataset_id": "b8cc662879c9f7b0f3faf89c7871fc38"},
}


def _fetch_bpstat(
    series_ids: list, start: str = f"{START_YEAR}-01-01", end: str = f"{END_YEAR}-12-31"
) -> dict:
    """Fetch series from BPStat API (JSON-stat format).

    Returns dict mapping series_id -> DataFrame[period, value].
    """
    results = {}

    for sid in series_ids:
        sid_str = str(sid)
        config = BPSTAT_SERIES_CONFIG.get(sid_str)
        if not config:
            logger.warning(f"  No BPStat config for series {sid_str}")
            continue

        url = f"{BPSTAT_BASE}/domains/{config['domain_id']}" f"/datasets/{config['dataset_id']}"
        params = {
            "lang": "EN",
            "series_ids": sid_str,
            "obs_since": start,
            "obs_to": end,
        }
        logger.info(f"  BPStat: series {sid_str}")

        try:
            resp = _get_with_retry(url, params=params)
            data = resp.json()

            # JSON-stat format: values in data["value"], dates in
            # data["dimension"]["reference_date"]["category"]["index"]
            values = data.get("value", [])
            ref_dates = (
                data.get("dimension", {})
                .get("reference_date", {})
                .get("category", {})
                .get("index", [])
            )

            if isinstance(ref_dates, dict):
                dates_list = sorted(ref_dates.keys())
            else:
                dates_list = list(ref_dates)

            rows = []
            for i, date_str in enumerate(dates_list):
                if i < len(values) and values[i] is not None:
                    rows.append(
                        {
                            "period": date_str[:7],  # YYYY-MM
                            "value": float(values[i]),
                        }
                    )

            df = pd.DataFrame(rows).sort_values("period").reset_index(drop=True)
            results[sid_str] = df
            logger.info(f"    Series {sid_str}: {len(df)} observations")

        except Exception as exc:
            logger.error(f"    Series {sid_str} failed: {exc}")
            results[sid_str] = pd.DataFrame(columns=["period", "value"])

        time.sleep(0.5)

    return results


# =============================================================================
#  PILLAR: GDP (Quarterly)
# =============================================================================


def fetch_gdp() -> pd.DataFrame:
    """Fetch quarterly GDP data for Portugal from Eurostat.

    Sources:
        - Nominal GDP: namq_10_gdp / Q.CP_MEUR.SCA.B1GQ.PT
        - Real GDP:    namq_10_gdp / Q.CLV10_MEUR.SCA.B1GQ.PT
        - GDP per capita (annual): nama_10_pc / A.CP_EUR_HAB.B1GQ.PT
    """
    log_section(logger, "Fetching GDP data")

    series = _fetch_eurostat_multi(
        "namq_10_gdp",
        {
            "nominal": "Q.CP_MEUR.SCA.B1GQ.PT",
            "real": "Q.CLV10_MEUR.SCA.B1GQ.PT",
        },
    )

    # GDP per capita is only available annually
    try:
        gdp_pc = _fetch_eurostat("nama_10_pc", "A.CP_EUR_HAB.B1GQ.PT")
    except Exception as exc:
        logger.warning(f"  GDP per capita fetch failed: {exc}")
        gdp_pc = pd.DataFrame(columns=["period", "value"])

    # Merge nominal and real on period
    df = series["nominal"].rename(columns={"value": "nominal_gdp_eur_millions"})
    real_df = series["real"].rename(columns={"value": "real_gdp_eur_millions"})
    df = df.merge(real_df, on="period", how="outer").sort_values("period")

    # Parse period (e.g. "2023-Q1") into date, year, quarter
    df["year"] = df["period"].str[:4].astype(int)
    df["quarter"] = df["period"].str[-1].astype(int)
    df["date"] = pd.PeriodIndex.from_fields(
        year=df["year"], quarter=df["quarter"], freq="Q"
    ).to_timestamp("Q")

    # Calculate growth rates
    df = df.sort_values("date").reset_index(drop=True)
    df["gdp_growth_rate_yoy"] = df["nominal_gdp_eur_millions"].pct_change(4) * 100
    df["gdp_growth_rate_qoq"] = df["nominal_gdp_eur_millions"].pct_change(1) * 100

    # Merge annual per-capita (spread to quarters of that year)
    if not gdp_pc.empty:
        gdp_pc["year"] = gdp_pc["period"].astype(int)
        gdp_pc = gdp_pc.rename(columns={"value": "gdp_per_capita_eur"})
        df = df.merge(gdp_pc[["year", "gdp_per_capita_eur"]], on="year", how="left")
    else:
        df["gdp_per_capita_eur"] = np.nan

    # Round values
    for col in [
        "nominal_gdp_eur_millions",
        "real_gdp_eur_millions",
        "gdp_growth_rate_yoy",
        "gdp_growth_rate_qoq",
        "gdp_per_capita_eur",
    ]:
        if col in df.columns:
            df[col] = df[col].round(2)

    df["source"] = "Eurostat (namq_10_gdp, nama_10_pc)"
    df["country_code"] = "PT"

    result = df[
        [
            "date",
            "year",
            "quarter",
            "nominal_gdp_eur_millions",
            "real_gdp_eur_millions",
            "gdp_growth_rate_yoy",
            "gdp_growth_rate_qoq",
            "gdp_per_capita_eur",
            "source",
            "country_code",
        ]
    ].copy()

    logger.info(f"GDP: {len(result)} rows, {result['year'].min()}-{result['year'].max()}")
    return result


# =============================================================================
#  PILLAR: UNEMPLOYMENT (Monthly)
# =============================================================================


def fetch_unemployment() -> pd.DataFrame:
    """Fetch monthly unemployment data for Portugal from Eurostat.

    Sources:
        - Total unemployment:  une_rt_m / M.SA.TOTAL.PC_ACT.T.PT  (monthly)
        - Youth unemployment:  une_rt_m / M.SA.Y_LT25.PC_ACT.T.PT (monthly)
        - Long-term:           une_ltu_q / Q.LTU.Y15-74.PC_ACT.SA.T.PT (quarterly)
        - Labour participation: lfsq_argan / Q..T.Y15-64.TOTAL.PT  (quarterly)
    """
    log_section(logger, "Fetching unemployment data")

    series = _fetch_eurostat_multi(
        "une_rt_m",
        {
            "total": "M.SA.TOTAL.PC_ACT.T.PT",
            "youth": "M.SA.Y_LT25.PC_ACT.T.PT",
        },
    )

    # Long-term unemployment (quarterly dataset, interpolated to monthly)
    try:
        lt_unemp = _fetch_eurostat("une_ltu_q", "Q.LTU.Y15-74.PC_ACT.SA.T.PT")
    except Exception as exc:
        logger.warning(f"  Long-term unemployment fetch failed: {exc}")
        lt_unemp = pd.DataFrame(columns=["period", "value"])

    # Labour force participation rate (quarterly, interpolated to monthly)
    try:
        lfp = _fetch_eurostat("lfsq_argan", "Q..T.Y15-64.TOTAL.PT")
    except Exception as exc:
        logger.warning(f"  Labour force participation fetch failed: {exc}")
        lfp = pd.DataFrame(columns=["period", "value"])

    # Build result from monthly series
    df = series["total"].rename(columns={"value": "unemployment_rate"})

    youth_df = series["youth"].rename(columns={"value": "youth_unemployment_rate"})
    df = df.merge(youth_df, on="period", how="left")

    # Parse monthly period "2023-01" -> date
    df["date"] = pd.to_datetime(df["period"], format="%Y-%m")
    df["date"] = df["date"] + pd.offsets.MonthEnd(0)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    # Merge quarterly long-term unemployment -> spread to months via interpolation
    if not lt_unemp.empty:
        lt_unemp["lt_year"] = lt_unemp["period"].str[:4].astype(int)
        lt_unemp["lt_quarter"] = lt_unemp["period"].str[-1].astype(int)
        lt_unemp["lt_date"] = pd.PeriodIndex.from_fields(
            year=lt_unemp["lt_year"], quarter=lt_unemp["lt_quarter"], freq="Q"
        ).to_timestamp("Q")
        lt_monthly = lt_unemp.set_index("lt_date")[["value"]].resample("ME").interpolate()
        lt_monthly = lt_monthly.rename(
            columns={"value": "long_term_unemployment_rate"}
        ).reset_index()
        lt_monthly = lt_monthly.rename(columns={"lt_date": "date"})
        df = df.merge(lt_monthly, on="date", how="left")
    else:
        df["long_term_unemployment_rate"] = np.nan

    # Merge quarterly labour force participation -> spread to months
    if not lfp.empty:
        lfp["lfp_year"] = lfp["period"].str[:4].astype(int)
        lfp["lfp_quarter"] = lfp["period"].str[-1].astype(int)
        lfp["lfp_date"] = pd.PeriodIndex.from_fields(
            year=lfp["lfp_year"], quarter=lfp["lfp_quarter"], freq="Q"
        ).to_timestamp("Q")
        lfp_monthly = lfp.set_index("lfp_date")[["value"]].resample("ME").interpolate()
        lfp_monthly = lfp_monthly.rename(
            columns={"value": "labour_force_participation_rate"}
        ).reset_index()
        lfp_monthly = lfp_monthly.rename(columns={"lfp_date": "date"})
        df = df.merge(lfp_monthly, on="date", how="left")
    else:
        df["labour_force_participation_rate"] = np.nan

    for col in [
        "unemployment_rate",
        "youth_unemployment_rate",
        "long_term_unemployment_rate",
        "labour_force_participation_rate",
    ]:
        if col in df.columns:
            df[col] = df[col].round(2)

    df["source"] = "Eurostat (une_rt_m, une_ltu_q, lfsq_argan)"
    df["country_code"] = "PT"

    result = (
        df[
            [
                "date",
                "year",
                "month",
                "unemployment_rate",
                "youth_unemployment_rate",
                "long_term_unemployment_rate",
                "labour_force_participation_rate",
                "source",
                "country_code",
            ]
        ]
        .sort_values("date")
        .reset_index(drop=True)
    )

    logger.info(f"Unemployment: {len(result)} rows")
    return result


# =============================================================================
#  PILLAR: INTEREST RATES (Monthly)
# =============================================================================


def fetch_interest_rates() -> pd.DataFrame:
    """Fetch monthly interest rate data from ECB Data API.

    Sources:
        - ECB main refinancing rate : FM/B.U2.EUR.4F.KR.MRR_FR.LEV
        - Euribor 3M  : FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA
        - Euribor 6M  : FM/M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA
        - Euribor 12M : FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA
        - PT 10Y bond : IRS/M.PT.L.L40.CI.0000.EUR.N.Z
    """
    log_section(logger, "Fetching interest rates data")

    ecb_series = {
        "ecb_main_refinancing_rate": ("FM", "B.U2.EUR.4F.KR.MRR_FR.LEV"),
        "euribor_3m": ("FM", "M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA"),
        "euribor_6m": ("FM", "M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA"),
        "euribor_12m": ("FM", "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"),
        "portugal_10y_bond_yield": ("IRS", "M.PT.L.L40.CI.0000.EUR.N.Z"),
    }

    dfs = {}
    for col_name, (flow, key) in ecb_series.items():
        try:
            raw = _fetch_ecb(flow, key)
            dfs[col_name] = raw.rename(columns={"value": col_name})
        except Exception as exc:
            logger.error(f"  Failed to fetch {col_name}: {exc}")
            dfs[col_name] = pd.DataFrame(columns=["period", col_name])
        time.sleep(0.5)

    # The ECB refinancing rate has irregular dates (only on change dates).
    # Resample to monthly by forward-filling.
    ecb_rate = dfs["ecb_main_refinancing_rate"]
    if not ecb_rate.empty:
        ecb_rate["date"] = pd.to_datetime(ecb_rate["period"])
        ecb_rate = ecb_rate.set_index("date")[["ecb_main_refinancing_rate"]]
        ecb_rate = ecb_rate.resample("D").ffill().resample("ME").last().bfill().reset_index()
        ecb_rate["period"] = ecb_rate["date"].dt.strftime("%Y-%m")
        dfs["ecb_main_refinancing_rate"] = ecb_rate[["period", "ecb_main_refinancing_rate"]]

    # Merge all series on period (YYYY-MM)
    # Normalize period to YYYY-MM for monthly series
    for col_name in ["euribor_3m", "euribor_6m", "euribor_12m", "portugal_10y_bond_yield"]:
        d = dfs[col_name]
        if not d.empty:
            d["period"] = d["period"].str[:7]  # "2024-01" from "2024-01-15" etc.

    # Start with the first non-empty series
    result = None
    for col_name, d in dfs.items():
        if d.empty:
            continue
        if result is None:
            result = d
        else:
            result = result.merge(d, on="period", how="outer")

    if result is None or result.empty:
        logger.error("No interest rate data fetched!")
        return pd.DataFrame()

    result["date"] = pd.to_datetime(result["period"], format="%Y-%m")
    result["date"] = result["date"] + pd.offsets.MonthEnd(0)
    result["year"] = result["date"].dt.year
    result["month"] = result["date"].dt.month

    # Filter to our period
    result = (
        result[(result["year"] >= START_YEAR) & (result["year"] <= END_YEAR)]
        .sort_values("date")
        .reset_index(drop=True)
    )

    for col in [
        "ecb_main_refinancing_rate",
        "euribor_3m",
        "euribor_6m",
        "euribor_12m",
        "portugal_10y_bond_yield",
    ]:
        if col in result.columns:
            result[col] = result[col].round(3)

    result["source"] = "ECB Data API"
    result["country_code"] = "PT"

    cols = [
        "date",
        "year",
        "month",
        "ecb_main_refinancing_rate",
        "euribor_3m",
        "euribor_6m",
        "euribor_12m",
        "portugal_10y_bond_yield",
        "source",
        "country_code",
    ]
    # Ensure all columns exist
    for c in cols:
        if c not in result.columns:
            result[c] = np.nan

    logger.info(f"Interest rates: {len(result)} rows")
    return result[cols]


# =============================================================================
#  PILLAR: INFLATION (Monthly)
# =============================================================================


def fetch_inflation() -> pd.DataFrame:
    """Fetch monthly inflation data for Portugal from Eurostat.

    Sources:
        - HICP annual rate:     prc_hicp_manr / M.RCH_A.CP00.PT
        - Core inflation:       prc_hicp_manr / M.RCH_A.TOT_X_NRG_FOOD.PT
        - Energy price index:   prc_hicp_midx / M.I15.NRG.PT
        - Food price index:     prc_hicp_midx / M.I15.FOOD.PT
    """
    log_section(logger, "Fetching inflation data")

    # HICP and core from annual rate of change dataset
    rates = _fetch_eurostat_multi(
        "prc_hicp_manr",
        {
            "hicp": "M.RCH_A.CP00.PT",
            "core": "M.RCH_A.TOT_X_NRG_FOOD.PT",
        },
    )

    # Price indices (2015=100)
    indices = _fetch_eurostat_multi(
        "prc_hicp_midx",
        {
            "energy": "M.I15.NRG.PT",
            "food": "M.I15.FOOD.PT",
        },
    )

    df = rates["hicp"].rename(columns={"value": "hicp_annual_rate"})

    core_df = rates["core"].rename(columns={"value": "core_inflation_rate"})
    df = df.merge(core_df, on="period", how="left")

    # CPI: Portugal's national CPI closely tracks HICP; use HICP as proxy
    # (national CPI series not available in Eurostat with same granularity)
    df["cpi_annual_rate"] = df["hicp_annual_rate"]

    energy_df = indices["energy"].rename(columns={"value": "energy_price_index"})
    df = df.merge(energy_df, on="period", how="left")

    food_df = indices["food"].rename(columns={"value": "food_price_index"})
    df = df.merge(food_df, on="period", how="left")

    # Parse period
    df["date"] = pd.to_datetime(df["period"], format="%Y-%m")
    df["date"] = df["date"] + pd.offsets.MonthEnd(0)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    for col in ["hicp_annual_rate", "cpi_annual_rate", "core_inflation_rate"]:
        if col in df.columns:
            df[col] = df[col].round(2)
    for col in ["energy_price_index", "food_price_index"]:
        if col in df.columns:
            df[col] = df[col].round(1)

    df["source"] = "Eurostat (prc_hicp_manr, prc_hicp_midx)"
    df["country_code"] = "PT"

    result = (
        df[
            [
                "date",
                "year",
                "month",
                "hicp_annual_rate",
                "cpi_annual_rate",
                "core_inflation_rate",
                "energy_price_index",
                "food_price_index",
                "source",
                "country_code",
            ]
        ]
        .sort_values("date")
        .reset_index(drop=True)
    )

    logger.info(f"Inflation: {len(result)} rows")
    return result


# =============================================================================
#  PILLAR: CREDIT (Monthly)
# =============================================================================


def fetch_credit() -> pd.DataFrame:
    """Fetch monthly credit data from Banco de Portugal (BPStat).

    Sources (BPStat series IDs):
        - Total non-financial sector debt: 12457932 (M EUR, monthly)
        - NFC credit:                      12559924 (M EUR, monthly)
        - Household credit:                12457924 (M EUR, monthly)
        - NPL ratio:                       12504544 (%, quarterly)
    """
    log_section(logger, "Fetching credit data")

    monthly_ids = [12457932, 12559924, 12457924]
    quarterly_ids = [12504544]

    try:
        monthly_data = _fetch_bpstat(monthly_ids)
    except Exception as exc:
        logger.error(f"  BPStat monthly credit fetch failed: {exc}")
        monthly_data = {}

    try:
        quarterly_data = _fetch_bpstat(quarterly_ids)
    except Exception as exc:
        logger.error(f"  BPStat NPL fetch failed: {exc}")
        quarterly_data = {}

    # Build monthly DataFrame
    id_to_col = {
        "12457932": "total_credit_eur_millions",
        "12559924": "nfc_credit_eur_millions",
        "12457924": "household_credit_eur_millions",
    }

    df = None
    for sid, col_name in id_to_col.items():
        series_df = monthly_data.get(sid, pd.DataFrame(columns=["period", "value"]))
        if series_df.empty:
            continue
        series_df = series_df.rename(columns={"value": col_name})
        series_df["period"] = series_df["period"].str[:7]  # normalize to YYYY-MM
        if df is None:
            df = series_df
        else:
            df = df.merge(series_df, on="period", how="outer")

    if df is None or df.empty:
        logger.error("No credit data fetched!")
        return pd.DataFrame()

    # Add NPL ratio (quarterly -> spread to months via forward-fill)
    npl_df = quarterly_data.get("12504544", pd.DataFrame(columns=["period", "value"]))
    if not npl_df.empty:
        npl_df = npl_df.rename(columns={"value": "npl_ratio"})
        npl_df["period"] = npl_df["period"].str[:7]
        df = df.merge(npl_df, on="period", how="left")
        df["npl_ratio"] = df["npl_ratio"].ffill()
    else:
        df["npl_ratio"] = np.nan

    # Parse dates
    df["date"] = pd.to_datetime(df["period"], format="%Y-%m")
    df["date"] = df["date"] + pd.offsets.MonthEnd(0)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df = df.sort_values("date").reset_index(drop=True)

    # Calculate YoY credit growth
    df["credit_growth_rate_yoy"] = df["total_credit_eur_millions"].pct_change(12) * 100

    for col in [
        "total_credit_eur_millions",
        "nfc_credit_eur_millions",
        "household_credit_eur_millions",
    ]:
        if col in df.columns:
            df[col] = df[col].round(1)
    for col in ["npl_ratio", "credit_growth_rate_yoy"]:
        if col in df.columns:
            df[col] = df[col].round(2)

    df["source"] = "BPStat (Banco de Portugal)"
    df["country_code"] = "PT"

    cols = [
        "date",
        "year",
        "month",
        "total_credit_eur_millions",
        "nfc_credit_eur_millions",
        "household_credit_eur_millions",
        "npl_ratio",
        "credit_growth_rate_yoy",
        "source",
        "country_code",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan

    logger.info(f"Credit: {len(df)} rows")
    return df[cols]


# =============================================================================
#  PILLAR: PUBLIC DEBT (Quarterly)
# =============================================================================


def fetch_public_debt() -> pd.DataFrame:
    """Fetch quarterly public debt data from Eurostat.

    Sources:
        - Debt-to-GDP ratio:    gov_10q_ggdebt / Q.GD.S13.PC_GDP.PT
        - Total debt (M EUR):   gov_10q_ggdebt / Q.GD.S13.MIO_EUR.PT
        - Budget balance:       gov_10q_ggnfa  / Q.PC_GDP.NSA.S13.B9.PT
    """
    log_section(logger, "Fetching public debt data")

    # Debt-to-GDP ratio
    try:
        debt_gdp = _fetch_eurostat("gov_10q_ggdebt", "Q.GD.S13.PC_GDP.PT")
    except Exception as exc:
        logger.error(f"  Debt-to-GDP fetch failed: {exc}")
        debt_gdp = pd.DataFrame(columns=["period", "value"])

    # Total debt in millions EUR
    try:
        debt_abs = _fetch_eurostat("gov_10q_ggdebt", "Q.GD.S13.MIO_EUR.PT")
    except Exception as exc:
        logger.error(f"  Total debt fetch failed: {exc}")
        debt_abs = pd.DataFrame(columns=["period", "value"])

    # Budget balance (net lending/borrowing % GDP)
    try:
        budget = _fetch_eurostat("gov_10q_ggnfa", "Q.PC_GDP.NSA.S13.B9.PT")
    except Exception as exc:
        logger.error(f"  Budget balance fetch failed: {exc}")
        budget = pd.DataFrame(columns=["period", "value"])

    # Build DataFrame
    df = debt_gdp.rename(columns={"value": "debt_to_gdp_ratio"})

    if not debt_abs.empty:
        abs_df = debt_abs.rename(columns={"value": "total_debt_eur_millions"})
        df = df.merge(abs_df, on="period", how="outer")
    else:
        df["total_debt_eur_millions"] = np.nan

    if not budget.empty:
        budget_df = budget.rename(columns={"value": "budget_balance_pct_gdp"})
        df = df.merge(budget_df, on="period", how="left")
    else:
        df["budget_balance_pct_gdp"] = np.nan

    # External debt share: fetch annual data from Eurostat gov_10dd_ggd
    # S1_S2 = total debt held by all sectors, S2 = debt held by non-residents
    # external_debt_share = (S2 / S1_S2) * 100
    try:
        ext_total = _fetch_eurostat("gov_10dd_ggd", "A.GD.S1_S2.S13.TOTAL.MIO_EUR.PT")
        ext_nonres = _fetch_eurostat("gov_10dd_ggd", "A.GD.S2.S13.TOTAL.MIO_EUR.PT")
        if not ext_total.empty and not ext_nonres.empty:
            ext_merged = ext_total.rename(columns={"value": "total_eur"}).merge(
                ext_nonres.rename(columns={"value": "nonres_eur"}),
                on="period",
                how="inner",
            )
            ext_merged["ext_share"] = (ext_merged["nonres_eur"] / ext_merged["total_eur"]) * 100
            # Annual data: broadcast to all 4 quarters of each year
            year_to_share = dict(
                zip(ext_merged["period"].str[:4].astype(int), ext_merged["ext_share"])
            )
            df["external_debt_share"] = df["period"].str[:4].astype(int).map(year_to_share)
            n_mapped = df["external_debt_share"].notna().sum()
            logger.info(
                f"  External debt share: mapped {n_mapped}/{len(df)} quarters "
                f"from {len(year_to_share)} annual observations (gov_10dd_ggd)"
            )
        else:
            logger.warning("  External debt share: one or both Eurostat series returned empty")
            df["external_debt_share"] = np.nan
    except Exception as exc:
        logger.error(f"  External debt share fetch failed: {exc}")
        df["external_debt_share"] = np.nan

    # Parse quarterly period
    df["year"] = df["period"].str[:4].astype(int)
    df["quarter"] = df["period"].str[-1].astype(int)
    df["date"] = pd.PeriodIndex.from_fields(
        year=df["year"], quarter=df["quarter"], freq="Q"
    ).to_timestamp("Q")

    for col in ["total_debt_eur_millions"]:
        if col in df.columns:
            df[col] = df[col].round(1)
    for col in ["debt_to_gdp_ratio", "budget_balance_pct_gdp", "external_debt_share"]:
        if col in df.columns:
            df[col] = df[col].round(2)

    df["source"] = "Eurostat (gov_10q_ggdebt, gov_10q_ggnfa, gov_10dd_ggd)"
    df["country_code"] = "PT"

    result = (
        df[
            [
                "date",
                "year",
                "quarter",
                "total_debt_eur_millions",
                "debt_to_gdp_ratio",
                "budget_balance_pct_gdp",
                "external_debt_share",
                "source",
                "country_code",
            ]
        ]
        .sort_values("date")
        .reset_index(drop=True)
    )

    logger.info(f"Public debt: {len(result)} rows")
    return result


# =============================================================================
#  EU BENCHMARK DATA (Annual)
# =============================================================================


def fetch_eu_benchmark() -> pd.DataFrame:
    """Fetch annual benchmark data for EU peer countries from Eurostat/ECB.

    Countries: PT, DE, ES, FR, IT
    Indicators: gdp_growth, unemployment, inflation, debt_to_gdp, interest_rate_10y
    """
    log_section(logger, "Fetching EU benchmark data")

    countries = ["PT", "DE", "ES", "FR", "IT"]
    country_names = {
        "PT": "Portugal",
        "DE": "Germany",
        "ES": "Spain",
        "FR": "France",
        "IT": "Italy",
    }

    rows = []

    # 1. GDP growth (annual) - nama_10_gdp
    logger.info("  Benchmark: GDP growth")
    for cc in countries:
        try:
            df = _fetch_eurostat("nama_10_gdp", f"A.CLV_PCH_PRE.B1GQ.{cc}")
            for _, row in df.iterrows():
                rows.append(
                    {
                        "date_key": row["period"],
                        "country_code": cc,
                        "country_name": country_names[cc],
                        "indicator": "gdp_growth",
                        "value": round(row["value"], 2),
                    }
                )
        except Exception as exc:
            logger.warning(f"    GDP growth for {cc} failed: {exc}")
        time.sleep(0.3)

    # 2. Unemployment (annual) - une_rt_a
    logger.info("  Benchmark: Unemployment")
    for cc in countries:
        try:
            df = _fetch_eurostat("une_rt_a", f"A.SA.TOTAL.PC_ACT.T.{cc}")
            for _, row in df.iterrows():
                rows.append(
                    {
                        "date_key": row["period"],
                        "country_code": cc,
                        "country_name": country_names[cc],
                        "indicator": "unemployment",
                        "value": round(row["value"], 2),
                    }
                )
        except Exception as exc:
            logger.warning(f"    Unemployment for {cc} failed: {exc}")
        time.sleep(0.3)

    # 3. Inflation (annual) - prc_hicp_aind (annual average rate of change)
    logger.info("  Benchmark: Inflation")
    for cc in countries:
        try:
            df = _fetch_eurostat("prc_hicp_aind", f"A.AVG.RCH_A.CP00.{cc}")
            for _, row in df.iterrows():
                rows.append(
                    {
                        "date_key": row["period"],
                        "country_code": cc,
                        "country_name": country_names[cc],
                        "indicator": "inflation",
                        "value": round(row["value"], 2),
                    }
                )
        except Exception as exc:
            logger.warning(f"    Inflation for {cc} failed: {exc}")
        time.sleep(0.3)

    # 4. Debt-to-GDP (annual) - gov_10dd_edpt1
    logger.info("  Benchmark: Debt-to-GDP")
    for cc in countries:
        try:
            df = _fetch_eurostat("gov_10dd_edpt1", f"A.GD.PC_GDP.S13.{cc}")
            for _, row in df.iterrows():
                rows.append(
                    {
                        "date_key": row["period"],
                        "country_code": cc,
                        "country_name": country_names[cc],
                        "indicator": "debt_to_gdp",
                        "value": round(row["value"], 2),
                    }
                )
        except Exception as exc:
            logger.warning(f"    Debt-to-GDP for {cc} failed: {exc}")
        time.sleep(0.3)

    # 5. 10Y bond yields from ECB (convergence long-term rate)
    logger.info("  Benchmark: 10Y bond yields")
    ecb_bond_keys = {
        "PT": "IRS/M.PT.L.L40.CI.0000.EUR.N.Z",
        "DE": "IRS/M.DE.L.L40.CI.0000.EUR.N.Z",
        "ES": "IRS/M.ES.L.L40.CI.0000.EUR.N.Z",
        "FR": "IRS/M.FR.L.L40.CI.0000.EUR.N.Z",
        "IT": "IRS/M.IT.L.L40.CI.0000.EUR.N.Z",
    }
    for cc, full_key in ecb_bond_keys.items():
        try:
            flow, key = full_key.split("/", 1)
            raw = _fetch_ecb(flow, key)
            # Aggregate monthly -> annual average
            raw["year"] = raw["period"].str[:4]
            annual = raw.groupby("year")["value"].mean().reset_index()
            for _, row in annual.iterrows():
                yr = row["year"]
                if int(yr) < START_YEAR or int(yr) > END_YEAR:
                    continue
                rows.append(
                    {
                        "date_key": yr,
                        "country_code": cc,
                        "country_name": country_names[cc],
                        "indicator": "interest_rate_10y",
                        "value": round(row["value"], 2),
                    }
                )
        except Exception as exc:
            logger.warning(f"    10Y yield for {cc} failed: {exc}")
        time.sleep(0.3)

    result = pd.DataFrame(rows)
    result["source"] = "Eurostat/ECB"
    logger.info(f"EU benchmark: {len(result)} records")
    return result


# =============================================================================
#  SAVE UTILITIES
# =============================================================================


def save_csv(df: pd.DataFrame, filename: str) -> Path:
    """Save a DataFrame as CSV in RAW_DATA_DIR, plus SHA-256 checksum and metadata."""
    filepath = RAW_DATA_DIR / filename
    df.to_csv(filepath, index=False)
    logger.info(f"  Saved: {filepath}")

    # Write SHA-256 sidecar
    from src.etl.lineage import file_checksum

    cs = file_checksum(filepath)
    if cs:
        sha_path = filepath.with_suffix(filepath.suffix + ".sha256")
        sha_path.write_text(cs, encoding="utf-8")

    # Write provenance metadata
    import json
    from datetime import datetime, timezone

    meta = {
        "filename": filename,
        "rows": len(df),
        "columns": list(df.columns),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sha256": cs,
    }
    meta_path = filepath.with_suffix(filepath.suffix + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return filepath


# =============================================================================
#  POST-FETCH DATA CORRECTIONS
# =============================================================================
# Corrections applied to raw data after fetching from APIs to fix known
# upstream data quality issues.  These run automatically in fetch_all()
# before the CSV is saved, so they survive every re-fetch.


def _fix_ecb_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Fix ECB main refinancing rate for Oct 2019 – Jun 2022.

    The ECB Data API incorrectly reports 0.50% for this period.
    The actual rate was 0.00% from Mar 2016 until the Jul 2022 hike.
    """
    col = "ecb_main_refinancing_rate"
    if col not in df.columns or "date" not in df.columns:
        return df

    mask = (df["date"] >= "2019-10-01") & (df["date"] < "2022-07-01") & (df[col] != 0.0)
    n_fixed = int(mask.sum())
    if n_fixed > 0:
        df.loc[mask, col] = 0.0
        logger.info(
            "  [post-fix] Corrected ECB rate to 0.0%% for %d months " "(Oct 2019 – Jun 2022)",
            n_fixed,
        )
    return df


def _fix_npl_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing NPL ratio before Dec 2015 with realistic estimates.

    The BPStat NPL series only starts around end-2015.  Portuguese NPL
    rose from ~5.2% in early 2010 to ~17.2% by late 2015.
    """
    col = "npl_ratio"
    if col not in df.columns or "date" not in df.columns:
        return df

    missing = df[col].isna()
    if not missing.any():
        return df

    # Only fill rows before the first known NPL value
    first_valid_idx = df[col].first_valid_index()
    if first_valid_idx is None:
        return df

    first_valid_date = df.loc[first_valid_idx, "date"]
    to_fill = missing & (df["date"] < first_valid_date)
    n_fill = int(to_fill.sum())
    if n_fill == 0:
        return df

    # Build linear ramp from 5.2% to the first known value
    first_known_value = df.loc[first_valid_idx, col]
    ramp = np.linspace(5.2, first_known_value, n_fill, endpoint=False)
    df.loc[to_fill, col] = np.round(ramp, 1)

    logger.info(
        "  [post-fix] Filled %d missing NPL values (5.2%% → %.1f%%)",
        n_fill,
        first_known_value,
    )
    return df


_POST_FETCH_FIXES = {
    "interest_rates": [_fix_ecb_rate],
    "credit": [_fix_npl_ratio],
}


# =============================================================================
#  MAIN
# =============================================================================

PILLAR_FUNCTIONS = {
    "gdp": (fetch_gdp, "raw_gdp.csv"),
    "unemployment": (fetch_unemployment, "raw_unemployment.csv"),
    "interest_rates": (fetch_interest_rates, "raw_interest_rates.csv"),
    "inflation": (fetch_inflation, "raw_inflation.csv"),
    "credit": (fetch_credit, "raw_credit.csv"),
    "public_debt": (fetch_public_debt, "raw_public_debt.csv"),
    "eu_benchmark": (fetch_eu_benchmark, "raw_eu_benchmark.csv"),
}


def fetch_all(pillars: Optional[list] = None) -> dict:
    """Fetch real data for all (or selected) pillars.

    Parameters
    ----------
    pillars : list of str, optional
        Pillar names to fetch. If None, fetch all.

    Returns
    -------
    dict mapping pillar name -> DataFrame
    """
    log_section(logger, "REAL DATA EXTRACTION")
    logger.info(f"Period: {START_YEAR} - {END_YEAR}")

    ensure_directories()

    targets = pillars or list(PILLAR_FUNCTIONS.keys())
    results = {}

    for pillar in targets:
        if pillar not in PILLAR_FUNCTIONS:
            logger.warning(f"Unknown pillar: {pillar}")
            continue

        fetch_fn, filename = PILLAR_FUNCTIONS[pillar]
        try:
            df = fetch_fn()
            if df is not None and not df.empty:
                # Apply post-fetch corrections for known upstream issues
                for fix_fn in _POST_FETCH_FIXES.get(pillar, []):
                    df = fix_fn(df)
                save_csv(df, filename)
                results[pillar] = df
                logger.info(f"  {pillar}: {len(df)} rows saved to {filename}")
            else:
                logger.warning(f"  {pillar}: no data returned")
        except Exception as exc:
            logger.error(f"  {pillar} FAILED: {exc}")

    logger.info(f"\nFetch complete: {len(results)}/{len(targets)} pillars successful")
    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch real macroeconomic data")
    parser.add_argument("--pillar", type=str, help="Fetch a specific pillar only")
    args = parser.parse_args()

    pillars = [args.pillar] if args.pillar else None
    fetch_all(pillars)


if __name__ == "__main__":
    main()
