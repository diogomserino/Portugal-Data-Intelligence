"""
Portugal Data Intelligence - Synthetic Data Generation
========================================================
Generates realistic synthetic macroeconomic data for Portugal (2010-2025)
based on real historical reference values.

Approach:
    1. Define annual/quarterly/monthly reference points from actual data.
    2. Use numpy linear interpolation (np.interp) to create smooth curves
       between the reference points.
    3. Add controlled random noise and seasonal patterns appropriate to
       each indicator.
    4. Save each pillar as a CSV in data/raw/.

All random operations use seed 42 for full reproducibility.

Author: Portugal Data Intelligence
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
# Add project root to path so config is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import END_YEAR, RAW_DATA_DIR, START_YEAR, ensure_directories
from src.utils.logger import get_logger

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = get_logger("generate_data")

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RNG_SEED = 42
rng = np.random.default_rng(RNG_SEED)

# ---------------------------------------------------------------------------
# Portugal population estimates (millions) for per-capita calculations
# ---------------------------------------------------------------------------
POPULATION = {
    2010: 10.57,
    2011: 10.56,
    2012: 10.51,
    2013: 10.46,
    2014: 10.40,
    2015: 10.36,
    2016: 10.33,
    2017: 10.30,
    2018: 10.28,
    2019: 10.30,
    2020: 10.31,
    2021: 10.33,
    2022: 10.35,
    2023: 10.47,
    2024: 10.55,
    2025: 10.61,
}


# =============================================================================
#  HELPER UTILITIES
# =============================================================================


def _quarterly_dates(start_year: int, end_year: int) -> pd.DatetimeIndex:
    """Return end-of-quarter dates from start_year Q1 to end_year Q4."""
    return pd.date_range(
        start=f"{start_year}-03-31",
        end=f"{end_year}-12-31",
        freq="QE",
    )


def _monthly_dates(start_year: int, end_year: int) -> pd.DatetimeIndex:
    """Return end-of-month dates from start_year-01 to end_year-12."""
    return pd.date_range(
        start=f"{start_year}-01-31",
        end=f"{end_year}-12-31",
        freq="ME",
    )


def _interp_annual_to_quarterly(
    years: np.ndarray, values: np.ndarray, dates: pd.DatetimeIndex
) -> np.ndarray:
    """Interpolate annual reference values to quarterly resolution.

    Parameters
    ----------
    years : array of reference years (e.g. [2010, 2011, ...])
    values : array of reference values at those years
    dates : quarterly DatetimeIndex to interpolate onto

    Returns
    -------
    Interpolated array of len(dates).
    """
    # Convert dates to fractional years (e.g. 2010.25 for end of Q1)
    frac_years = dates.year + (dates.month / 12.0)
    result: np.ndarray = np.asarray(np.interp(frac_years, years.astype(float), values))
    return result


def _interp_annual_to_monthly(
    years: np.ndarray, values: np.ndarray, dates: pd.DatetimeIndex
) -> np.ndarray:
    """Interpolate annual reference values to monthly resolution."""
    frac_years = dates.year + (dates.month / 12.0)
    result: np.ndarray = np.asarray(np.interp(frac_years, years.astype(float), values))
    return result


def _add_noise(series: np.ndarray, scale: float) -> np.ndarray:
    """Add Gaussian noise with given standard deviation (scale)."""
    result: np.ndarray = series + rng.normal(0, scale, size=len(series))
    return result


def _seasonal_component(dates: pd.DatetimeIndex, amplitudes: dict) -> np.ndarray:
    """Create a seasonal component from month-level amplitudes.

    Parameters
    ----------
    dates : DatetimeIndex
    amplitudes : dict mapping month (1-12) to additive seasonal factor

    Returns
    -------
    Array of seasonal adjustments.
    """
    return np.array([amplitudes.get(d.month, 0.0) for d in dates])


# =============================================================================
#  GDP GENERATION  (Quarterly)
# =============================================================================


def generate_gdp() -> pd.DataFrame:
    """Generate quarterly GDP data for Portugal 2010-2025.

    Columns produced:
        date, year, quarter, nominal_gdp_eur_millions, real_gdp_eur_millions,
        gdp_growth_rate_yoy, gdp_growth_rate_qoq, gdp_per_capita_eur,
        source, country_code
    """
    logger.info("Generating GDP data ...")
    dates = _quarterly_dates(START_YEAR, END_YEAR)

    # -- Reference annual nominal GDP (EUR billions) -----------------------
    ref_years = np.arange(2010, 2026)
    ref_nominal_b = np.array(
        [
            172,
            176,
            169,
            170,
            174,
            180,
            187,
            195,
            205,
            214,
            200,
            215,
            240,
            255,
            268,
            278,
        ]
    )

    # Interpolate to quarterly (in EUR millions)
    nominal = _interp_annual_to_quarterly(ref_years, ref_nominal_b * 1000, dates)

    # Seasonal pattern: Q2/Q3 higher (tourism), Q1/Q4 lower
    q_season = {3: -0.015, 6: 0.012, 9: 0.018, 12: -0.010}
    seasonal = np.array([q_season.get(d.month, 0.0) for d in dates])
    nominal = nominal * (1 + seasonal)

    # Small noise (0.3 % of level)
    nominal = _add_noise(nominal, nominal.mean() * 0.003)

    # Quarterly values (divide annual by 4, already interpolated)
    nominal_q = nominal / 4.0

    # -- Real GDP (base 2015) ---------------------------------------------
    # Build a GDP deflator from the inflation data pattern
    ref_deflator = np.array(
        [
            0.95,
            0.96,
            0.96,
            0.95,
            0.96,
            1.00,
            1.01,
            1.02,
            1.04,
            1.05,
            1.06,
            1.07,
            1.15,
            1.20,
            1.23,
            1.25,
        ]
    )
    deflator = _interp_annual_to_quarterly(ref_years, ref_deflator, dates)
    real_q = nominal_q / deflator

    # -- Growth rates ------------------------------------------------------
    # Year-on-year (compare to same quarter previous year)
    yoy = np.full(len(dates), np.nan)
    for i in range(4, len(dates)):
        yoy[i] = (nominal_q[i] - nominal_q[i - 4]) / nominal_q[i - 4] * 100

    # Quarter-on-quarter
    qoq = np.full(len(dates), np.nan)
    for i in range(1, len(dates)):
        qoq[i] = (nominal_q[i] - nominal_q[i - 1]) / nominal_q[i - 1] * 100

    # -- Per capita --------------------------------------------------------
    pop_q = _interp_annual_to_quarterly(
        ref_years,
        np.array([POPULATION[y] for y in range(2010, 2026)]),
        dates,
    )
    # GDP per capita = annualised nominal GDP / population
    # NOTE: nominal_gdp_eur_millions in the output is QUARTERLY (nominal/4),
    # but per_capita is ANNUAL (nominal/pop). This is the standard convention
    # (per capita is always reported on an annual basis).
    per_capita = nominal / pop_q

    df = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "quarter": dates.quarter,
            "nominal_gdp_eur_millions": np.round(nominal_q, 1),
            "real_gdp_eur_millions": np.round(real_q, 1),
            "gdp_growth_rate_yoy": np.round(yoy, 2),
            "gdp_growth_rate_qoq": np.round(qoq, 2),
            "gdp_per_capita_eur": np.round(per_capita, 0),
            "source": "Synthetic (INE/Eurostat reference)",
            "country_code": "PT",
        }
    )

    logger.info(f"  GDP rows generated: {len(df)}")
    return df


# =============================================================================
#  UNEMPLOYMENT GENERATION  (Monthly)
# =============================================================================


def generate_unemployment() -> pd.DataFrame:
    """Generate monthly unemployment data for Portugal 2010-2025.

    Columns: date, year, month, unemployment_rate, youth_unemployment_rate,
             long_term_unemployment_rate, labour_force_participation_rate,
             source, country_code
    """
    logger.info("Generating unemployment data ...")
    dates = _monthly_dates(START_YEAR, END_YEAR)

    ref_years = np.arange(2010, 2026)
    ref_unemp = np.array(
        [
            10.8,
            12.7,
            15.5,
            16.2,
            13.9,
            12.4,
            11.1,
            8.9,
            7.0,
            6.5,
            7.0,
            6.6,
            6.0,
            6.5,
            6.4,
            6.2,
        ]
    )

    unemp = _interp_annual_to_monthly(ref_years, ref_unemp, dates)

    # Seasonal: higher in winter months (Jan, Feb, Dec), lower in summer
    season_amp = {
        1: 0.35,
        2: 0.25,
        3: 0.10,
        4: -0.05,
        5: -0.15,
        6: -0.25,
        7: -0.30,
        8: -0.35,
        9: -0.20,
        10: 0.05,
        11: 0.15,
        12: 0.30,
    }
    unemp += _seasonal_component(dates, season_amp)
    unemp = _add_noise(unemp, 0.12)
    unemp = np.clip(unemp, 3.0, 20.0)

    # Youth unemployment ~ 2.2x general rate
    youth = unemp * 2.2 + _add_noise(np.zeros(len(dates)), 0.3)
    youth = np.clip(youth, 8.0, 42.0)

    # Long-term unemployment ~ 0.45x general rate
    long_term = unemp * 0.45 + _add_noise(np.zeros(len(dates)), 0.15)
    long_term = np.clip(long_term, 1.0, 10.0)

    # Labour force participation rate (55-60%)
    ref_lfp = np.array(
        [
            55.5,
            56.0,
            56.2,
            56.0,
            56.5,
            57.0,
            57.5,
            58.0,
            58.5,
            58.8,
            57.5,
            58.0,
            59.0,
            59.5,
            59.8,
            60.0,
        ]
    )
    lfp = _interp_annual_to_monthly(ref_years, ref_lfp, dates)
    lfp = _add_noise(lfp, 0.1)
    lfp = np.clip(lfp, 54.0, 62.0)

    df = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "month": dates.month,
            "unemployment_rate": np.round(unemp, 2),
            "youth_unemployment_rate": np.round(youth, 2),
            "long_term_unemployment_rate": np.round(long_term, 2),
            "labour_force_participation_rate": np.round(lfp, 2),
            "source": "Synthetic (INE/Eurostat reference)",
            "country_code": "PT",
        }
    )

    logger.info(f"  Unemployment rows generated: {len(df)}")
    return df


# =============================================================================
#  INTEREST RATES GENERATION  (Monthly)
# =============================================================================


def generate_interest_rates() -> pd.DataFrame:
    """Generate monthly interest rate data for Portugal 2010-2025.

    Columns: date, year, month, ecb_main_refinancing_rate, euribor_3m,
             euribor_6m, euribor_12m, portugal_10y_bond_yield,
             source, country_code
    """
    logger.info("Generating interest rates data ...")
    dates = _monthly_dates(START_YEAR, END_YEAR)

    # -- ECB main refinancing rate (key reference points) ------------------
    # Use semi-annual reference points for more precision during hike cycle
    ecb_ref_times = np.array(
        [
            2010.0,
            2011.0,
            2011.5,
            2012.0,
            2012.5,
            2013.0,
            2013.5,
            2014.0,
            2014.5,
            2015.0,
            2016.0,
            2017.0,
            2018.0,
            2019.0,
            2020.0,
            2021.0,
            2022.0,
            2022.5,
            2022.75,
            2023.0,
            2023.5,
            2023.75,
            2024.0,
            2024.5,
            2024.75,
            2025.0,
            2025.5,
            2026.0,
        ]
    )
    ecb_ref_vals = np.array(
        [
            1.00,
            1.00,
            1.50,
            1.00,
            0.75,
            0.75,
            0.50,
            0.25,
            0.15,
            0.05,
            0.00,
            0.00,
            0.00,
            0.00,
            0.00,
            0.00,
            0.00,
            0.50,
            1.25,
            2.50,
            4.00,
            4.50,
            4.50,
            4.25,
            3.65,
            3.15,
            2.90,
            2.65,
        ]
    )

    frac = dates.year + dates.month / 12.0
    ecb = np.interp(frac, ecb_ref_times, ecb_ref_vals)
    ecb = _add_noise(ecb, 0.01)
    ecb = np.clip(ecb, -0.1, 5.0)

    # Euribor rates follow ECB with a spread
    euribor_3m = ecb + rng.normal(0.10, 0.03, len(dates))
    euribor_6m = ecb + rng.normal(0.20, 0.04, len(dates))
    euribor_12m = ecb + rng.normal(0.35, 0.05, len(dates))

    # Clip Euribor: they went negative during zero-rate era
    euribor_3m = np.where(ecb < 0.1, np.clip(euribor_3m, -0.55, 0.2), euribor_3m)
    euribor_6m = np.where(ecb < 0.1, np.clip(euribor_6m, -0.45, 0.3), euribor_6m)
    euribor_12m = np.where(ecb < 0.1, np.clip(euribor_12m, -0.35, 0.4), euribor_12m)

    # -- Portugal 10-year bond yield ---------------------------------------
    bond_ref_times = np.array(
        [
            2010.0,
            2010.5,
            2011.0,
            2011.5,
            2012.0,
            2012.25,
            2012.5,
            2013.0,
            2013.5,
            2014.0,
            2014.5,
            2015.0,
            2016.0,
            2017.0,
            2018.0,
            2019.0,
            2019.5,
            2020.0,
            2020.5,
            2021.0,
            2021.5,
            2022.0,
            2022.5,
            2023.0,
            2023.5,
            2024.0,
            2024.5,
            2025.0,
            2025.5,
            2026.0,
        ]
    )
    bond_ref_vals = np.array(
        [
            4.0,
            5.5,
            7.0,
            10.5,
            13.0,
            12.0,
            9.5,
            6.5,
            6.0,
            5.0,
            3.8,
            2.8,
            3.2,
            3.0,
            1.8,
            0.8,
            0.4,
            0.3,
            0.4,
            0.2,
            0.4,
            1.2,
            2.5,
            3.2,
            3.5,
            3.2,
            3.0,
            3.0,
            2.9,
            2.8,
        ]
    )

    bond_yield = np.interp(frac, bond_ref_times, bond_ref_vals)
    bond_yield = _add_noise(bond_yield, 0.08)
    bond_yield = np.clip(bond_yield, 0.0, 15.0)

    df = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "month": dates.month,
            "ecb_main_refinancing_rate": np.round(ecb, 3),
            "euribor_3m": np.round(euribor_3m, 3),
            "euribor_6m": np.round(euribor_6m, 3),
            "euribor_12m": np.round(euribor_12m, 3),
            "portugal_10y_bond_yield": np.round(bond_yield, 3),
            "source": "Synthetic (ECB/BdP reference)",
            "country_code": "PT",
        }
    )

    logger.info(f"  Interest rates rows generated: {len(df)}")
    return df


# =============================================================================
#  INFLATION GENERATION  (Monthly)
# =============================================================================


def generate_inflation() -> pd.DataFrame:
    """Generate monthly inflation data for Portugal 2010-2025.

    Columns: date, year, month, hicp_annual_rate, cpi_annual_rate,
             core_inflation_rate, energy_price_index, food_price_index,
             source, country_code
    """
    logger.info("Generating inflation data ...")
    dates = _monthly_dates(START_YEAR, END_YEAR)

    # -- Headline HICP (year-on-year %) ------------------------------------
    # Use sub-annual reference for the 2022 spike
    hicp_ref_times = np.array(
        [
            2010.0,
            2010.5,
            2011.0,
            2011.5,
            2012.0,
            2012.5,
            2013.0,
            2013.5,
            2014.0,
            2014.5,
            2015.0,
            2015.5,
            2016.0,
            2016.5,
            2017.0,
            2017.5,
            2018.0,
            2018.5,
            2019.0,
            2019.5,
            2020.0,
            2020.5,
            2021.0,
            2021.5,
            2022.0,
            2022.25,
            2022.5,
            2022.75,
            2023.0,
            2023.5,
            2024.0,
            2024.5,
            2025.0,
            2025.5,
            2026.0,
        ]
    )
    hicp_ref_vals = np.array(
        [
            1.4,
            2.0,
            3.5,
            3.0,
            2.8,
            1.5,
            0.4,
            0.2,
            -0.2,
            -0.1,
            0.5,
            0.6,
            0.6,
            0.7,
            1.4,
            1.3,
            1.2,
            1.5,
            0.3,
            0.5,
            -0.1,
            0.0,
            0.5,
            1.3,
            3.5,
            5.5,
            8.0,
            9.5,
            8.2,
            4.5,
            2.8,
            2.4,
            2.1,
            2.0,
            1.9,
        ]
    )

    frac = dates.year + dates.month / 12.0
    hicp = np.interp(frac, hicp_ref_times, hicp_ref_vals)

    # Seasonal: slight uptick in spring/summer
    infl_season = {
        1: -0.10,
        2: -0.05,
        3: 0.05,
        4: 0.10,
        5: 0.08,
        6: 0.05,
        7: 0.03,
        8: -0.02,
        9: -0.05,
        10: -0.03,
        11: -0.02,
        12: -0.04,
    }
    hicp += _seasonal_component(dates, infl_season)
    hicp = _add_noise(hicp, 0.08)

    # CPI closely tracks HICP with tiny differences
    cpi = hicp + rng.normal(0.05, 0.06, len(dates))

    # Core inflation: smoother, lower during energy spikes
    core_ref_vals = np.array(
        [
            0.8,
            1.2,
            2.0,
            1.5,
            1.5,
            0.8,
            0.3,
            0.2,
            0.0,
            0.1,
            0.5,
            0.5,
            0.6,
            0.6,
            1.1,
            1.0,
            0.9,
            1.1,
            0.4,
            0.5,
            0.0,
            0.2,
            0.5,
            1.0,
            2.5,
            3.5,
            5.0,
            5.5,
            5.5,
            4.0,
            3.0,
            2.5,
            2.2,
            2.0,
            1.8,
        ]
    )
    core = np.interp(frac, hicp_ref_times, core_ref_vals)
    core = _add_noise(core, 0.06)

    # Energy price index (base 2015 = 100)
    energy_ref = np.array(
        [
            2010.0,
            2012.0,
            2014.0,
            2016.0,
            2018.0,
            2020.0,
            2021.0,
            2022.0,
            2022.5,
            2023.0,
            2024.0,
            2025.0,
            2026.0,
        ]
    )
    energy_vals = np.array(
        [
            95,
            110,
            105,
            100,
            108,
            92,
            105,
            135,
            155,
            130,
            115,
            110,
            108,
        ]
    )
    energy = np.interp(frac, energy_ref, energy_vals)
    energy = _add_noise(energy, 1.5)

    # Food price index (base 2015 = 100)
    food_ref = np.array(
        [
            2010.0,
            2012.0,
            2014.0,
            2016.0,
            2018.0,
            2020.0,
            2021.0,
            2022.0,
            2023.0,
            2024.0,
            2025.0,
            2026.0,
        ]
    )
    food_vals = np.array(
        [
            92,
            96,
            98,
            100,
            104,
            108,
            110,
            122,
            135,
            138,
            140,
            141,
        ]
    )
    food = np.interp(frac, food_ref, food_vals)
    food = _add_noise(food, 0.8)

    df = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "month": dates.month,
            "hicp_annual_rate": np.round(hicp, 2),
            "cpi_annual_rate": np.round(cpi, 2),
            "core_inflation_rate": np.round(core, 2),
            "energy_price_index": np.round(energy, 1),
            "food_price_index": np.round(food, 1),
            "source": "Synthetic (INE/Eurostat reference)",
            "country_code": "PT",
        }
    )

    logger.info(f"  Inflation rows generated: {len(df)}")
    return df


# =============================================================================
#  CREDIT GENERATION  (Monthly)
# =============================================================================


def generate_credit() -> pd.DataFrame:
    """Generate monthly credit data for Portugal 2010-2025.

    Columns: date, year, month, total_credit_eur_millions,
             nfc_credit_eur_millions, household_credit_eur_millions,
             npl_ratio, credit_growth_rate_yoy, source, country_code
    """
    logger.info("Generating credit data ...")
    dates = _monthly_dates(START_YEAR, END_YEAR)

    # -- Total credit (EUR billions) ---------------------------------------
    ref_years = np.arange(2010, 2026)
    ref_total_b = np.array(
        [
            290,
            282,
            272,
            262,
            253,
            240,
            230,
            232,
            235,
            238,
            240,
            242,
            245,
            248,
            254,
            260,
        ]
    )

    total = _interp_annual_to_monthly(ref_years, ref_total_b * 1000, dates)
    total = _add_noise(total, 400)  # ~400M noise on 230-290B
    total = np.clip(total, 200_000, 320_000)

    # NFC credit ~ 37% of total
    nfc_share = _interp_annual_to_monthly(
        ref_years,
        np.array(
            [
                0.40,
                0.39,
                0.38,
                0.38,
                0.37,
                0.36,
                0.35,
                0.35,
                0.36,
                0.36,
                0.36,
                0.36,
                0.37,
                0.37,
                0.37,
                0.37,
            ]
        ),
        dates,
    )
    nfc = total * nfc_share + _add_noise(np.zeros(len(dates)), 200)

    # Household credit ~ remainder
    household = total - nfc + _add_noise(np.zeros(len(dates)), 150)

    # -- NPL ratio ---------------------------------------------------------
    ref_npl = np.array(
        [
            3.0,
            5.0,
            7.5,
            10.0,
            12.5,
            14.5,
            17.0,
            15.0,
            11.5,
            8.5,
            6.0,
            4.8,
            3.8,
            3.2,
            3.0,
            2.8,
        ]
    )
    npl = _interp_annual_to_monthly(ref_years, ref_npl, dates)
    npl = _add_noise(npl, 0.1)
    npl = np.clip(npl, 1.5, 19.0)

    # -- Year-on-year credit growth ----------------------------------------
    yoy = np.full(len(dates), np.nan)
    for i in range(12, len(dates)):
        yoy[i] = (total[i] - total[i - 12]) / total[i - 12] * 100

    df = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "month": dates.month,
            "total_credit_eur_millions": np.round(total, 1),
            "nfc_credit_eur_millions": np.round(nfc, 1),
            "household_credit_eur_millions": np.round(household, 1),
            "npl_ratio": np.round(npl, 2),
            "credit_growth_rate_yoy": np.round(yoy, 2),
            "source": "Synthetic (BdP reference)",
            "country_code": "PT",
        }
    )

    logger.info(f"  Credit rows generated: {len(df)}")
    return df


# =============================================================================
#  PUBLIC DEBT GENERATION  (Quarterly)
# =============================================================================


def generate_public_debt() -> pd.DataFrame:
    """Generate quarterly public debt data for Portugal 2010-2025.

    Columns: date, year, quarter, total_debt_eur_millions,
             debt_to_gdp_ratio, budget_balance_pct_gdp,
             external_debt_share, source, country_code
    """
    logger.info("Generating public debt data ...")
    dates = _quarterly_dates(START_YEAR, END_YEAR)

    ref_years = np.arange(2010, 2026)

    # -- Debt-to-GDP ratio (%) ---------------------------------------------
    ref_debt_gdp = np.array(
        [
            96.0,
            111.0,
            126.0,
            129.0,
            131.0,
            129.0,
            131.0,
            126.0,
            122.0,
            117.0,
            135.0,
            125.0,
            113.0,
            107.0,
            100.0,
            98.0,
        ]
    )
    debt_gdp = _interp_annual_to_quarterly(ref_years, ref_debt_gdp, dates)
    debt_gdp = _add_noise(debt_gdp, 0.3)

    # -- Nominal GDP for debt level calculation (annual EUR billions) ------
    ref_nominal_b = np.array(
        [
            172,
            176,
            169,
            170,
            174,
            180,
            187,
            195,
            205,
            214,
            200,
            215,
            240,
            255,
            268,
            278,
        ]
    )
    gdp_annual = _interp_annual_to_quarterly(ref_years, ref_nominal_b * 1000, dates)

    # Total debt (EUR millions) = debt_to_gdp * gdp_annual / 100
    total_debt = debt_gdp / 100.0 * gdp_annual
    total_debt = _add_noise(total_debt, 300)

    # -- Budget balance (% of GDP) -----------------------------------------
    ref_budget = np.array(
        [
            -10.0,
            -7.4,
            -5.7,
            -4.8,
            -7.2,
            -4.4,
            -2.0,
            -3.0,
            -0.4,
            -0.3,
            -5.8,
            -2.9,
            -0.3,
            1.2,
            0.8,
            0.5,
        ]
    )
    budget = _interp_annual_to_quarterly(ref_years, ref_budget, dates)
    budget = _add_noise(budget, 0.15)

    # -- External debt share (%) -------------------------------------------
    ref_ext = np.array(
        [
            48.0,
            50.0,
            52.0,
            53.0,
            54.0,
            53.0,
            52.0,
            50.0,
            49.0,
            48.0,
            50.0,
            49.0,
            47.0,
            46.0,
            45.0,
            45.0,
        ]
    )
    ext_share = _interp_annual_to_quarterly(ref_years, ref_ext, dates)
    ext_share = _add_noise(ext_share, 0.2)
    ext_share = np.clip(ext_share, 40.0, 58.0)

    df = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "quarter": dates.quarter,
            "total_debt_eur_millions": np.round(total_debt, 1),
            "debt_to_gdp_ratio": np.round(debt_gdp, 2),
            "budget_balance_pct_gdp": np.round(budget, 2),
            "external_debt_share": np.round(ext_share, 2),
            "source": "Synthetic (BdP/PORDATA reference)",
            "country_code": "PT",
        }
    )

    logger.info(f"  Public debt rows generated: {len(df)}")
    return df


# =============================================================================
#  SAVE AND SUMMARY UTILITIES
# =============================================================================


def save_csv(df: pd.DataFrame, filename: str) -> Path:
    """Save a DataFrame as CSV in RAW_DATA_DIR."""
    filepath = RAW_DATA_DIR / filename
    df.to_csv(filepath, index=False)
    logger.info(f"  Saved: {filepath}")
    return filepath


def print_summary(name: str, df: pd.DataFrame) -> None:
    """Print summary statistics for a generated dataset."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  Rows : {len(df)}")
    print(f"  Cols : {list(df.columns)}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    # Numeric columns summary
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        if col in ("year", "month", "quarter"):
            continue
        vals = df[col].dropna()
        if len(vals) == 0:
            continue
        print(
            f"  {col:40s}  min={vals.min():>10.2f}  max={vals.max():>10.2f}  mean={vals.mean():>10.2f}"
        )
    print()


# =============================================================================
#  MAIN
# =============================================================================


def main():
    """Generate all synthetic datasets and save to data/raw/."""
    logger.info("=" * 60)
    logger.info("Portugal Data Intelligence - Synthetic Data Generation")
    logger.info("=" * 60)

    # Ensure directories exist
    ensure_directories()
    logger.info(f"Output directory: {RAW_DATA_DIR}")

    # -- Generate each pillar ----------------------------------------------
    datasets = {}

    datasets["GDP"] = generate_gdp()
    save_csv(datasets["GDP"], "raw_gdp.csv")

    datasets["Unemployment"] = generate_unemployment()
    save_csv(datasets["Unemployment"], "raw_unemployment.csv")

    datasets["Interest Rates"] = generate_interest_rates()
    save_csv(datasets["Interest Rates"], "raw_interest_rates.csv")

    datasets["Inflation"] = generate_inflation()
    save_csv(datasets["Inflation"], "raw_inflation.csv")

    datasets["Credit"] = generate_credit()
    save_csv(datasets["Credit"], "raw_credit.csv")

    datasets["Public Debt"] = generate_public_debt()
    save_csv(datasets["Public Debt"], "raw_public_debt.csv")

    # -- Summary statistics ------------------------------------------------
    logger.info("Generation complete. Summary statistics:")
    for name, df in datasets.items():
        print_summary(name, df)

    total_rows = sum(len(df) for df in datasets.values())
    print(f"\nTotal rows generated across all pillars: {total_rows}")
    print(f"Files saved to: {RAW_DATA_DIR}\n")

    logger.info("All done.")


if __name__ == "__main__":
    main()
