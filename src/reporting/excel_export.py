"""
Portugal Data Intelligence - Excel Export
==========================================
Exports all macroeconomic pillar data to a structured Excel workbook:
  - One sheet per data pillar
  - A 'Summary' sheet with latest KPIs across all pillars
  - A 'Correlations' sheet with the pairwise correlation matrix

Usage:
    from src.reporting.excel_export import export_to_excel
    path = export_to_excel()
    # or via CLI: python main.py --mode reports --format excel
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import DATA_PILLARS, DATABASE_PATH, REPORTS_DIR
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

_PILLAR_QUERIES = {
    "gdp": """
        SELECT d.date_key, d.year, d.quarter,
               f.nominal_gdp, f.real_gdp, f.gdp_growth_yoy, f.gdp_growth_qoq, f.gdp_per_capita
        FROM fact_gdp f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year, d.quarter
    """,
    "unemployment": """
        SELECT d.date_key, d.year, d.month,
               f.unemployment_rate, f.youth_unemployment_rate,
               f.long_term_unemployment_rate, f.labour_force_participation_rate
        FROM fact_unemployment f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year, d.month
    """,
    "credit": """
        SELECT d.date_key, d.year, d.month,
               f.total_credit, f.credit_nfc, f.credit_households, f.npl_ratio
        FROM fact_credit f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year, d.month
    """,
    "interest_rates": """
        SELECT d.date_key, d.year, d.month,
               f.ecb_main_refinancing_rate, f.euribor_3m, f.euribor_6m,
               f.euribor_12m, f.portugal_10y_bond_yield
        FROM fact_interest_rates f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year, d.month
    """,
    "inflation": """
        SELECT d.date_key, d.year, d.month,
               f.hicp, f.cpi_estimated, f.core_inflation
        FROM fact_inflation f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year, d.month
    """,
    "public_debt": """
        SELECT d.date_key, d.year, d.quarter,
               f.total_debt, f.debt_to_gdp_ratio, f.budget_deficit,
               f.budget_deficit_annual, f.external_debt_share_estimated
        FROM fact_public_debt f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year, d.quarter
    """,
    "housing": """
        SELECT d.date_key, d.year,
               f.house_price_index, f.house_price_yoy_change,
               f.avg_price_per_sqm, f.housing_transactions, f.mortgage_new_loans
        FROM fact_housing f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year
    """,
    "labor_detail": """
        SELECT d.date_key, d.year,
               f.employment_services_pct, f.employment_industry_pct,
               f.employment_agriculture_pct, f.real_wage_index, f.labour_productivity_index
        FROM fact_labor_detail f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year
    """,
    "external_accounts": """
        SELECT d.date_key, d.year, d.quarter,
               f.trade_balance_pct_gdp, f.current_account_pct_gdp,
               f.reer_index, f.export_growth_yoy
        FROM fact_external_accounts f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year, d.quarter
    """,
    "fiscal": """
        SELECT d.date_key, d.year,
               f.total_revenue_pct_gdp, f.total_expenditure_pct_gdp,
               f.health_expenditure_pct, f.education_expenditure_pct,
               f.social_protection_pct, f.interest_payments_pct
        FROM fact_fiscal f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year
    """,
    "inequality": """
        SELECT d.date_key, d.year,
               f.gini_index, f.s80_s20_ratio, f.poverty_risk_rate, f.median_income_index
        FROM fact_inequality f JOIN dim_date d ON f.date_key=d.date_key
        ORDER BY d.year
    """,
}

_SUMMARY_METRICS = {
    "gdp": ("gdp_growth_yoy", "GDP Growth YoY (%)"),
    "unemployment": ("unemployment_rate", "Unemployment Rate (%)"),
    "credit": ("npl_ratio", "NPL Ratio (%)"),
    "interest_rates": ("portugal_10y_bond_yield", "10Y Bond Yield (%)"),
    "inflation": ("hicp", "HICP Inflation (%)"),
    "public_debt": ("debt_to_gdp_ratio", "Debt-to-GDP (%)"),
    "housing": ("house_price_yoy_change", "House Price Growth (%)"),
    "inequality": ("gini_index", "Gini Index"),
    "fiscal": ("total_expenditure_pct_gdp", "Gov. Expenditure (% GDP)"),
    "external_accounts": ("current_account_pct_gdp", "Current Account (% GDP)"),
}


def export_to_excel(
    db_path: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Export all pillar data to a timestamped Excel workbook.

    Parameters
    ----------
    db_path : str, optional
        Path to the SQLite database.
    output_dir : Path, optional
        Output directory. Defaults to reports/.

    Returns
    -------
    Path
        Path to the created Excel file.
    """
    db_path = db_path or str(DATABASE_PATH)
    output_dir = output_dir or REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"portugal_macro_{ts}.xlsx"

    pillar_dfs = {}
    summary_rows = []

    with get_connection(db_path) as conn:
        for pillar, query in _PILLAR_QUERIES.items():
            try:
                df = pd.read_sql(query, conn)
                pillar_dfs[pillar] = df
            except Exception as exc:
                logger.warning(f"Could not load {pillar} for Excel: {exc}")
                pillar_dfs[pillar] = pd.DataFrame()

    # Build summary row per pillar
    for pillar, (col, label) in _SUMMARY_METRICS.items():
        df = pillar_dfs.get(pillar, pd.DataFrame())
        if df.empty or col not in df.columns:
            summary_rows.append({"Indicator": label, "Latest Value": "N/A", "Period": "N/A"})
            continue
        latest = df[col].dropna()
        if latest.empty:
            summary_rows.append({"Indicator": label, "Latest Value": "N/A", "Period": "N/A"})
            continue
        summary_rows.append(
            {
                "Indicator": label,
                "Latest Value": round(float(latest.iloc[-1]), 2),
                "Period": str(df["date_key"].iloc[-1]) if "date_key" in df.columns else "—",
            }
        )

    summary_df = pd.DataFrame(summary_rows)

    # Build cross-pillar correlation matrix from primary metric columns
    corr_series: dict = {}
    for pillar, (col, label) in _SUMMARY_METRICS.items():
        df = pillar_dfs.get(pillar, pd.DataFrame())
        if df.empty or col not in df.columns:
            continue
        s = df[["date_key", col]].dropna().set_index("date_key")[col]
        corr_series[label] = s

    corr_df: pd.DataFrame
    if corr_series:
        corr_df = pd.DataFrame(corr_series).corr().round(3)
    else:
        corr_df = pd.DataFrame()

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Summary sheet
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        # Correlations sheet
        if not corr_df.empty:
            corr_df.to_excel(writer, sheet_name="Correlations")

        # One sheet per pillar
        for pillar, df in pillar_dfs.items():
            if df.empty:
                continue
            sheet_name = DATA_PILLARS.get(pillar, {}).get("name", pillar)[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    logger.info("Excel report saved to %s", output_path)
    return output_path
