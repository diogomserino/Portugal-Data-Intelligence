"""
Portugal Data Intelligence — HTML Report Generator
=====================================================
Generates a self-contained HTML report page styled as a Big4
consulting briefing / academic article.

All charts are embedded as base64 data URIs so the output HTML
is fully portable (single file, no external image references).

Usage:
    python dashboard/generate_report.py
    python dashboard/generate_report.py --output custom_path.html
"""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import plotly.graph_objects as go
    import plotly.offline as pyo

    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

# Tracks whether plotly.js has already been embedded, so the library is included
# from the CDN only once across the whole report; later charts reference it.
_PLOTLY_STATE = {"included": False}


def _plotly_include_arg():
    """Return "cdn" the first time plotly.js is needed, then False afterwards."""
    if _PLOTLY_STATE["included"]:
        return False
    _PLOTLY_STATE["included"] = True
    return "cdn"

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (
    CHARTS_DIR,
    DASHBOARD_PAGES_DIR,
    DATA_PILLARS,
    DATA_SOURCES,
    END_YEAR,
    INSIGHTS_DIR,
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
    START_YEAR,
    VERSION,
    ensure_directories,
)
from src.utils.logger import get_logger

logger = get_logger("generate_report")

# ---------------------------------------------------------------------------
# Human-readable column labels
# ---------------------------------------------------------------------------
_COLUMN_LABELS = {
    "nominal_gdp": "Nominal GDP (EUR M)",
    "real_gdp": "Real GDP (EUR M)",
    "gdp_growth_yoy": "GDP Growth YoY (%)",
    "gdp_growth_qoq": "GDP Growth QoQ (%)",
    "gdp_per_capita": "GDP per Capita (EUR)",
    "unemployment_rate": "Unemployment Rate (%)",
    "youth_unemployment_rate": "Youth Unemployment (%)",
    "long_term_unemployment_rate": "Long-term Unemp. (%)",
    "labour_force_participation_rate": "Labour Force Part. (%)",
    "total_credit": "Total Credit (EUR M)",
    "credit_nfc": "Credit to NFCs (EUR M)",
    "credit_households": "Household Credit (EUR M)",
    "npl_ratio": "NPL Ratio (%)",
    "ecb_main_refinancing_rate": "ECB Main Rate (%)",
    "euribor_3m": "Euribor 3M (%)",
    "euribor_6m": "Euribor 6M (%)",
    "euribor_12m": "Euribor 12M (%)",
    "portugal_10y_bond_yield": "PT 10Y Bond Yield (%)",
    "hicp": "HICP Inflation (%)",
    "cpi_estimated": "CPI Estimated (%)",
    "core_inflation": "Core Inflation (%)",
    "total_debt": "Total Debt (EUR M)",
    "debt_to_gdp_ratio": "Debt-to-GDP Ratio (%)",
    "budget_deficit": "Budget Balance Quarterly (% GDP)",
    "budget_deficit_annual": "Budget Balance Annual (% GDP)",
    "external_debt_share_estimated": "External Debt Share Est. (%)",
    # Housing
    "house_price_index": "House Price Index (2015=100)",
    "house_price_yoy_change": "House Price Growth YoY (%)",
    "avg_price_per_sqm": "Avg. Price per sqm (EUR)",
    "housing_transactions": "Housing Transactions",
    "mortgage_new_loans": "New Mortgage Loans (EUR M)",
    # Labour detail
    "employment_services_pct": "Employment: Services (%)",
    "employment_industry_pct": "Employment: Industry (%)",
    "employment_agriculture_pct": "Employment: Agriculture (%)",
    "real_wage_index": "Real Wage Index (2015=100)",
    "labour_productivity_index": "Labour Productivity Index (2015=100)",
    # External accounts
    "trade_balance_pct_gdp": "Trade Balance (% GDP)",
    "current_account_pct_gdp": "Current Account (% GDP)",
    "reer_index": "REER Index (2015=100)",
    "export_growth_yoy": "Export Growth YoY (%)",
    # Fiscal
    "total_revenue_pct_gdp": "Total Revenue (% GDP)",
    "total_expenditure_pct_gdp": "Total Expenditure (% GDP)",
    "health_expenditure_pct": "Health Expenditure (% GDP)",
    "education_expenditure_pct": "Education Expenditure (% GDP)",
    "social_protection_pct": "Social Protection (% GDP)",
    "interest_payments_pct": "Interest Payments (% GDP)",
    # Inequality
    "gini_index": "Gini Index",
    "s80_s20_ratio": "S80/S20 Income Ratio",
    "poverty_risk_rate": "Poverty Risk Rate (%)",
    "median_income_index": "Median Income Index (EU27=100)",
}

# Pillar display config: (pillar_key, title, chart_filename, icon)
_PILLAR_CONFIG = [
    ("gdp", "Gross Domestic Product", "gdp_evolution.png", ""),
    ("unemployment", "Labour Market & Employment", "unemployment_trends.png", ""),
    ("credit", "Credit to the Economy", "credit_portfolio.png", ""),
    ("interest_rates", "Interest Rate Environment", "interest_rate_environment.png", ""),
    ("inflation", "Price Stability & Inflation", "inflation_dashboard.png", ""),
    ("public_debt", "Public Debt Sustainability", "public_debt_sustainability.png", ""),
    ("housing", "Housing Market", "housing_trends.png", ""),
    ("labor_detail", "Labour Market Detail", "labor_detail_trends.png", ""),
    ("external_accounts", "External Competitiveness", "external_accounts_trends.png", ""),
    ("fiscal", "Fiscal Structure", "fiscal_trends.png", ""),
    ("inequality", "Inequality & Income", "inequality_trends.png", ""),
]

# Primary column per pillar for Plotly interactive chart
_PILLAR_PRIMARY_COL: Dict[str, str] = {
    "gdp": "gdp_growth_yoy",
    "unemployment": "unemployment_rate",
    "credit": "npl_ratio",
    "interest_rates": "portugal_10y_bond_yield",
    "inflation": "hicp",
    "public_debt": "debt_to_gdp_ratio",
    "housing": "house_price_yoy_change",
    "labor_detail": "real_wage_index",
    "external_accounts": "current_account_pct_gdp",
    "fiscal": "total_expenditure_pct_gdp",
    "inequality": "gini_index",
}

# KPI definitions: (pillar_key, column, label, format, suffix)
_KPI_DEFS = [
    ("gdp", "gdp_growth_yoy", "GDP Growth", ".1f", "%"),
    ("unemployment", "unemployment_rate", "Unemployment", ".1f", "%"),
    ("inflation", "hicp", "Inflation (HICP)", ".1f", "%"),
    ("public_debt", "debt_to_gdp_ratio", "Debt / GDP", ".1f", "%"),
    ("interest_rates", "portugal_10y_bond_yield", "10Y Bond Yield", ".2f", "%"),
    ("credit", "npl_ratio", "NPL Ratio", ".1f", "%"),
]


# =============================================================================
# DATA LOADING
# =============================================================================


def load_latest_briefing() -> Dict[str, Any]:
    """Load the most recent executive briefing JSON."""
    pattern = "executive_briefing_*.json"
    files = sorted(INSIGHTS_DIR.glob(pattern))
    if not files:
        logger.warning("No executive briefing found in %s", INSIGHTS_DIR)
        return {}
    latest = files[-1]
    logger.info("Loading briefing: %s", latest.name)
    with open(latest, "r", encoding="utf-8") as f:
        return json.load(f)


def load_kpi_values() -> Dict[str, Dict[str, float]]:
    """Load latest values from processed CSVs for KPI cards."""
    kpis: Dict[str, Dict[str, float]] = {}
    for pillar_key in DATA_PILLARS:
        csv_path = PROCESSED_DATA_DIR / f"{pillar_key}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if df.empty:
            continue
        last_row = df.iloc[-1]
        kpis[pillar_key] = {col: last_row[col] for col in df.columns if col != "date_key"}
        kpis[pillar_key]["_date"] = str(last_row.get("date_key", ""))
    return kpis


def load_dq_baseline() -> Dict[str, Dict[str, Dict[str, float]]]:
    """Load data quality baseline for statistics tables."""
    path = REPORTS_DIR / "data_quality" / "dq_baseline.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def encode_chart(filename: str) -> str:
    """Read a chart PNG and return a base64 data URI."""
    path = CHARTS_DIR / filename
    if not path.exists():
        logger.warning("Chart not found: %s", path)
        return ""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _make_plotly_timeseries(pillar_key: str, title: str, primary_col: str) -> str:
    """Build an interactive Plotly timeseries div for a pillar.

    Returns an HTML string (the Plotly div) or empty string if unavailable.
    """
    if not _HAS_PLOTLY or not primary_col:
        return ""
    csv_path = PROCESSED_DATA_DIR / f"{pillar_key}.csv"
    if not csv_path.exists():
        return ""
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return ""
    if df.empty or primary_col not in df.columns:
        return ""

    x_col = "date_key" if "date_key" in df.columns else df.columns[0]
    col_label = _COLUMN_LABELS.get(primary_col, primary_col.replace("_", " ").title())

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df[x_col],
            y=df[primary_col],
            mode="lines+markers",
            name=col_label,
            line={"color": "#1A1A2E", "width": 2},
            marker={"size": 4, "color": "#1A1A2E"},
            hovertemplate=f"<b>%{{x}}</b><br>{col_label}: %{{y:.2f}}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis={"title": "Period", "showgrid": True, "gridcolor": "#E8E8E8", "tickangle": -30},
        yaxis={"title": col_label, "showgrid": True, "gridcolor": "#E8E8E8"},
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": "DM Sans, 'Segoe UI', sans-serif", "size": 12},
        margin={"l": 60, "r": 20, "t": 20, "b": 60},
        height=320,
        hovermode="x unified",
        showlegend=False,
    )
    try:
        return pyo.plot(
            fig,
            output_type="div",
            include_plotlyjs=_plotly_include_arg(),
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            },
        )
    except Exception:
        return ""


# =============================================================================
# CSS DESIGN SYSTEM
# =============================================================================

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');

:root {
  --navy: #1C1C1E;
  --dark-slate: #2C2C2C;
  --deep-red: #9B2226;
  --forest-green: #2D7A40;
  --warm-gold: #D4A373;
  --steel-blue: #1D7A43;
  --off-white: #FFFFFF;
  --light-gray: #F5F5F5;
  --border: #D0D0D0;
  --medium-gray: #888;
  --risk-low: #2D7A40;
  --risk-moderate: #D4A373;
  --risk-elevated: #E65100;
  --risk-high: #9B2226;
  --font-heading: 'DM Sans', 'Segoe UI', -apple-system, sans-serif;
  --font-body: 'DM Sans', 'Segoe UI', -apple-system, sans-serif;
  --max-width: 1100px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: var(--font-body);
  font-size: 16px;
  line-height: 1.7;
  color: var(--dark-slate);
  background: var(--off-white);
}

/* --- HERO --- */
.hero {
  background: linear-gradient(135deg, var(--navy) 0%, #282828 100%);
  color: #fff;
  padding: 4rem 2rem 3.5rem;
  text-align: center;
  position: relative;
  overflow: hidden;
}
/* Portuguese flag accent bar */
.hero::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(to right, #009B3A 38.5%, #FF0000 38.5%);
}
.hero h1 {
  font-family: var(--font-heading);
  font-size: 2.75rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  letter-spacing: -0.02em;
}
.hero .subtitle {
  font-size: 1.15rem;
  font-weight: 300;
  opacity: 0.85;
  margin-bottom: 1.5rem;
}
.hero .meta {
  font-size: 0.85rem;
  opacity: 0.65;
  margin-bottom: 2rem;
}
.hero .executive-summary {
  max-width: 800px;
  margin: 0 auto;
  text-align: left;
  font-size: 0.95rem;
  line-height: 1.8;
  opacity: 0.9;
  border-left: 3px solid var(--warm-gold);
  padding-left: 1.5rem;
}
/* Hero KPI pills */
.hero-metrics {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.5rem;
  margin: 1.5rem 0 0;
}
.hm-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.8rem;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  letter-spacing: 0.02em;
}
.hm-pill.positive { background: rgba(45, 122, 64, 0.5); border-color: rgba(45,122,64,0.7); }
.hm-pill.negative { background: rgba(155, 34, 38, 0.5); border-color: rgba(155,34,38,0.7); }
.hm-pill.moderate { background: rgba(212, 163, 115, 0.3); border-color: rgba(212,163,115,0.5); }
.hm-pill .pill-label { opacity: 0.75; font-size: 0.72rem; }

/* --- TOC --- */
.toc {
  max-width: var(--max-width);
  margin: 2rem auto;
  padding: 1.5rem 2rem;
  background: var(--light-gray);
  border-radius: 8px;
}
.toc h2 {
  font-family: var(--font-heading);
  font-size: 1.1rem;
  color: var(--navy);
  margin-bottom: 0.75rem;
}
.toc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.4rem 2rem;
}
.toc a {
  color: var(--steel-blue);
  text-decoration: none;
  font-size: 0.9rem;
  padding: 0.2rem 0;
  display: block;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}
.toc a:hover { border-bottom-color: var(--steel-blue); }

/* --- MAIN CONTENT --- */
main {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0 2rem;
}

/* --- KPI DASHBOARD --- */
.kpi-dashboard { margin: 2.5rem 0; }
.kpi-dashboard h2 {
  font-family: var(--font-heading);
  font-size: 1.5rem;
  color: var(--navy);
  margin-bottom: 1.5rem;
  padding-left: 1rem;
  border-left: 4px solid var(--warm-gold);
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}
.kpi-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.25rem 1rem;
  text-align: center;
  border-top: 3px solid var(--steel-blue);
  transition: box-shadow 0.2s, transform 0.15s;
}
.kpi-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.1); transform: translateY(-2px); }
/* Semantic KPI colors */
.kpi-card.positive { border-top-color: var(--forest-green); }
.kpi-card.moderate { border-top-color: var(--warm-gold); }
.kpi-card.negative { border-top-color: var(--deep-red); }
.kpi-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--navy);
  line-height: 1.2;
}
.kpi-value.positive { color: var(--forest-green); }
.kpi-value.moderate { color: #9a6d00; }
.kpi-value.negative { color: var(--deep-red); }
.kpi-label {
  font-size: 0.78rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--medium-gray);
  margin-top: 0.4rem;
}
.kpi-period {
  font-size: 0.7rem;
  color: var(--medium-gray);
  margin-top: 0.2rem;
}
.kpi-trend {
  font-size: 0.78rem;
  font-weight: 600;
  margin-top: 0.35rem;
}
.kpi-trend.positive { color: var(--forest-green); }
.kpi-trend.moderate { color: #9a6d00; }
.kpi-trend.negative { color: var(--deep-red); }

/* --- PILLAR SECTIONS --- */
.pillar-section {
  margin: 3rem 0;
  padding-top: 1rem;
}
.pillar-section h2 {
  font-family: var(--font-heading);
  font-size: 1.6rem;
  color: var(--navy);
  padding-left: 1rem;
  border-left: 4px solid var(--warm-gold);
  margin-bottom: 1.25rem;
}
.pillar-section h3 {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--navy);
  margin: 1.5rem 0 0.75rem;
}
.pillar-narrative {
  margin-bottom: 1.5rem;
  white-space: pre-line;
}
.pillar-narrative p { margin-bottom: 0.8rem; }

figure {
  margin: 1.5rem 0;
  text-align: center;
}
figure img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  border: 1px solid var(--border);
}
figcaption {
  font-size: 0.8rem;
  color: var(--medium-gray);
  font-style: italic;
  margin-top: 0.5rem;
}

/* Findings list */
.key-findings { margin: 1rem 0; padding-left: 1.25rem; }
.key-findings li {
  margin-bottom: 0.5rem;
  font-size: 0.92rem;
  line-height: 1.6;
}

/* Risk callout */
.risk-callout {
  padding: 1rem 1.25rem;
  border-radius: 6px;
  background: var(--light-gray);
  border-left: 4px solid var(--medium-gray);
  margin: 1.25rem 0;
  font-size: 0.9rem;
}
.risk-callout.low { border-left-color: var(--risk-low); }
.risk-callout.moderate { border-left-color: var(--risk-moderate); }
.risk-callout.elevated { border-left-color: var(--risk-elevated); }
.risk-callout.high { border-left-color: var(--risk-high); }
.risk-callout strong { color: var(--navy); }

/* Stats table */
.stats-table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.88rem;
}
.stats-table th {
  background: var(--navy);
  color: #fff;
  font-weight: 500;
  text-align: left;
  padding: 0.6rem 0.8rem;
}
.stats-table th:not(:first-child) {
  text-align: right;
}
.stats-table td {
  padding: 0.5rem 0.8rem;
  border-bottom: 1px solid var(--border);
}
.stats-table tr:nth-child(even) td { background: var(--light-gray); }
.stats-table td:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; }

/* --- ANALYSIS SECTIONS --- */
.analysis-section {
  margin: 3rem 0;
  padding-top: 1rem;
}
.analysis-section h2 {
  font-family: var(--font-heading);
  font-size: 1.6rem;
  color: var(--navy);
  padding-left: 1rem;
  border-left: 4px solid var(--warm-gold);
  margin-bottom: 1.25rem;
}
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
  margin: 1.5rem 0;
}
.plotly-chart {
  margin: 1.5rem 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.plotly-chart .chart-caption {
  font-size: 0.8rem;
  color: var(--medium-gray);
  text-align: center;
  padding: 0.4rem 1rem 0.6rem;
  background: var(--light-gray);
}

/* --- RISK MATRIX --- */
.risk-matrix {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.9rem;
}
.risk-matrix th {
  background: var(--navy);
  color: #fff;
  font-weight: 500;
  padding: 0.6rem 1rem;
  text-align: left;
}
.risk-matrix td {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.risk-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #fff;
}
.risk-badge.low { background: var(--risk-low); }
.risk-badge.moderate { background: var(--risk-moderate); color: var(--navy); }
.risk-badge.elevated { background: var(--risk-elevated); }
.risk-badge.high { background: var(--risk-high); }

/* --- RECOMMENDATIONS --- */
.recommendations-list {
  counter-reset: rec;
  list-style: none;
  padding: 0;
}
.recommendations-list li {
  counter-increment: rec;
  padding: 1rem 1.25rem 1rem 3.5rem;
  margin-bottom: 0.75rem;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  position: relative;
  font-size: 0.92rem;
}
.recommendations-list li::before {
  content: counter(rec);
  position: absolute;
  left: 1rem;
  top: 1rem;
  width: 1.8rem;
  height: 1.8rem;
  background: var(--steel-blue);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
}

/* --- METHODOLOGY --- */
.methodology-section {
  margin: 3rem 0;
  padding: 2rem;
  background: var(--light-gray);
  border-radius: 8px;
}
.methodology-section h2 {
  font-family: var(--font-heading);
  font-size: 1.3rem;
  color: var(--navy);
  margin-bottom: 1rem;
}
.source-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  margin: 1rem 0;
}
.source-table th, .source-table td {
  padding: 0.5rem 0.8rem;
  border-bottom: 1px solid var(--border);
  text-align: left;
}
.source-table th { font-weight: 600; color: var(--navy); }

/* --- FOOTER --- */
footer {
  max-width: var(--max-width);
  margin: 3rem auto;
  padding: 2rem;
  border-top: 2px solid var(--navy);
  font-size: 0.8rem;
  color: var(--medium-gray);
  text-align: center;
}
footer .author { font-weight: 600; color: var(--navy); font-size: 0.9rem; }

/* --- SECTION SEPARATORS --- */
main > section + section {
  border-top: 1px solid #EBEBEB;
}

/* --- SCROLL PROGRESS BAR --- */
#progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  width: 0%;
  background: linear-gradient(90deg, #009B3A 0%, var(--warm-gold) 50%, var(--deep-red) 100%);
  z-index: 9999;
  transition: width 0.05s linear;
  pointer-events: none;
}

/* --- BACK TO TOP BUTTON --- */
#back-to-top {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  width: 2.75rem;
  height: 2.75rem;
  background: var(--navy);
  color: #fff;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: none;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  font-weight: 700;
  box-shadow: 0 3px 14px rgba(0, 0, 0, 0.28);
  z-index: 9998;
  transition: background 0.2s, transform 0.2s;
  line-height: 1;
}
#back-to-top:hover { background: var(--steel-blue); transform: translateY(-3px); }

/* --- RESPONSIVE --- */
@media (max-width: 768px) {
  .hero h1 { font-size: 1.8rem; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .chart-grid { grid-template-columns: 1fr !important; }
  main { padding: 0 1rem; }
  .hero-metrics { gap: 0.35rem; }
  .hm-pill { font-size: 0.72rem; padding: 0.25rem 0.6rem; }
}
@media (max-width: 480px) {
  .hero h1 { font-size: 1.5rem; }
  .hero .subtitle { font-size: 0.95rem; }
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .kpi-value { font-size: 1.65rem; }
  #back-to-top { bottom: 1rem; right: 1rem; width: 2.25rem; height: 2.25rem; font-size: 1rem; }
}

/* --- PRINT --- */
@media print {
  .hero { background: var(--navy) !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .toc { display: none; }
  .pillar-section, .analysis-section { page-break-before: auto; page-break-inside: avoid; }
  body { font-size: 11pt; }
  .kpi-card { border: 1px solid #ccc; }
  #progress-bar, #back-to-top { display: none !important; }
}
"""


# =============================================================================
# HTML RENDER FUNCTIONS
# =============================================================================


def _esc(text: str) -> str:
    """Basic HTML escaping."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _paragraphs(text: str) -> str:
    """Convert newline-separated text into <p> blocks."""
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    return "\n".join(f"<p>{_esc(p)}</p>" for p in parts)


def _risk_class(risk_text: str) -> str:
    """Extract risk level class from risk assessment text."""
    text = risk_text.upper()
    if "ELEVATED" in text or "OVERHEATING" in text:
        return "elevated"
    if "HIGH" in text:
        return "high"
    if "LOW" in text:
        return "low"
    return "moderate"


def render_hero(briefing: Dict, kpis: Optional[Dict] = None) -> str:
    title = briefing.get("title", "Portugal Macroeconomic Intelligence Briefing")
    date = briefing.get("date", datetime.now().strftime("%d %B %Y"))
    summary = briefing.get("overall_assessment", "")

    # Build metrics pills from KPI definitions
    pills_html = ""
    if kpis:
        pills = []
        _PILL_DEFS = [
            ("gdp", "gdp_growth_yoy", "GDP", ".1f", "%"),
            ("unemployment", "unemployment_rate", "Unemployment", ".1f", "%"),
            ("inflation", "hicp", "Inflation", ".1f", "%"),
            ("public_debt", "debt_to_gdp_ratio", "Debt/GDP", ".1f", "%"),
            ("interest_rates", "portugal_10y_bond_yield", "10Y Yield", ".2f", "%"),
        ]
        for pk, col, lbl, fmt, suf in _PILL_DEFS:
            val = kpis.get(pk, {}).get(col)
            if val is None:
                continue
            sem = _KPI_SEMANTIC.get(col, lambda v: "neutral")(val)
            arrow, _ = _kpi_trend(pk, col)
            formatted = f"{val:{fmt}}{suf}"
            pills.append(
                f'<span class="hm-pill {sem}">'
                f'<span class="pill-label">{lbl}</span>'
                f" {arrow} {formatted}"
                f"</span>"
            )
        if pills:
            pills_html = f'<div class="hero-metrics">{"".join(pills)}</div>'

    return f"""
<header class="hero">
  <h1>{_esc(title)}</h1>
  <div class="subtitle">Macroeconomic Analysis of the Portuguese Economy {START_YEAR}&ndash;{END_YEAR}</div>
  <div class="meta">{_esc(date)} &middot; Portugal Data Intelligence</div>
  <div class="executive-summary">
    {_paragraphs(summary)}
  </div>
  {pills_html}
</header>
"""


def render_toc() -> str:
    links = ['<a href="#key-indicators">Key Indicators</a>']
    for key, title, _, icon in _PILLAR_CONFIG:
        links.append(f'<a href="#{key}">{_esc(title)}</a>')
    links.extend(
        [
            '<a href="#executive-dashboard">Executive Dashboard</a>',
            '<a href="#cross-pillar">Cross-Pillar Analysis</a>',
            '<a href="#stl-decomposition">STL Decomposition</a>',
            '<a href="#forecasting">SARIMAX Forecasting</a>',
            '<a href="#benchmarking">EU Benchmarking</a>',
            '<a href="#regional">Regional Analysis (NUTS2)</a>',
            '<a href="#risk-matrix">Risk Matrix</a>',
            '<a href="#recommendations">Strategic Recommendations</a>',
            '<a href="#platform">Platform &amp; Tools</a>',
            '<a href="#methodology">Methodology</a>',
        ]
    )
    items = "\n    ".join(links)
    return f"""
<nav class="toc">
  <h2>Contents</h2>
  <div class="toc-grid">
    {items}
  </div>
</nav>
"""


_KPI_SEMANTIC = {
    "gdp_growth_yoy": lambda v: "positive" if v > 0 else "negative",
    "unemployment_rate": lambda v: "positive" if v < 8 else ("moderate" if v < 12 else "negative"),
    "hicp": lambda v: "positive" if 1.0 <= v <= 3.0 else ("moderate" if v <= 5.0 else "negative"),
    "debt_to_gdp_ratio": lambda v: (
        "positive" if v < 80 else ("moderate" if v < 100 else "negative")
    ),
    "portugal_10y_bond_yield": lambda v: (
        "positive" if v < 3.0 else ("moderate" if v < 5.0 else "negative")
    ),
    "npl_ratio": lambda v: "positive" if v < 5.0 else ("moderate" if v < 10.0 else "negative"),
}

_KPI_TREND_SIGN = {
    # positive direction = good
    "gdp_growth_yoy": 1,
    "hicp": 0,  # neutral — direction alone doesn't say "good"
    "unemployment_rate": -1,  # lower is better
    "debt_to_gdp_ratio": -1,
    "portugal_10y_bond_yield": -1,
    "npl_ratio": -1,
}


def _kpi_trend(pillar_key: str, col: str) -> tuple:
    """Return (arrow, trend_class) by comparing last two observations."""
    csv_path = PROCESSED_DATA_DIR / f"{pillar_key}.csv"
    if not csv_path.exists():
        return "", "neutral"
    try:
        series = pd.read_csv(csv_path)[col].dropna()
        if len(series) < 2:
            return "", "neutral"
        delta = float(series.iloc[-1]) - float(series.iloc[-2])
        if abs(delta) < 1e-9:
            return "―", "neutral"
        sign = _KPI_TREND_SIGN.get(col, 1)
        arrow = "▲" if delta > 0 else "▼"
        # "good" if direction matches preferred sign
        is_good = (delta > 0 and sign == 1) or (delta < 0 and sign == -1)
        cls = "positive" if is_good else ("moderate" if sign == 0 else "negative")
        return arrow, cls
    except Exception:
        return "", "neutral"


def render_kpi_dashboard(kpis: Dict) -> str:
    cards = []
    for pillar_key, col, label, fmt, suffix in _KPI_DEFS:
        pillar_data = kpis.get(pillar_key, {})
        value = pillar_data.get(col)
        period = pillar_data.get("_date", "")
        if value is not None:
            formatted = f"{value:{fmt}}{suffix}"
            sem_cls = _KPI_SEMANTIC.get(col, lambda v: "neutral")(value)
            arrow, trend_cls = _kpi_trend(pillar_key, col)
            trend_html = (
                f'<div class="kpi-trend {trend_cls}">{arrow} vs prev</div>' if arrow else ""
            )
        else:
            formatted = "N/A"
            sem_cls = "neutral"
            trend_html = ""
        cards.append(
            f'<div class="kpi-card {sem_cls}">'
            f'<div class="kpi-value {sem_cls}">{formatted}</div>'
            f'<div class="kpi-label">{_esc(label)}</div>'
            f'<div class="kpi-period">{_esc(period)}</div>'
            f"{trend_html}"
            f"</div>"
        )

    return f"""
<section id="key-indicators" class="kpi-dashboard">
  <h2>Key Indicators &mdash; Latest Values</h2>
  <div class="kpi-grid">
    {"".join(cards)}
  </div>
</section>
"""


def render_stats_table(pillar_key: str, baseline: Dict) -> str:
    """Render a statistics table from DQ baseline data."""
    stats = baseline.get(pillar_key, {})
    if not stats:
        return ""
    rows = []
    for col, values in stats.items():
        label = _COLUMN_LABELS.get(col, col)
        mean = values.get("mean", 0)
        std = values.get("std", 0)
        median = values.get("median", 0)
        # Format large numbers differently
        if abs(mean) > 1000:
            rows.append(
                f"<tr><td>{_esc(label)}</td>"
                f"<td>{mean:,.0f}</td><td>{std:,.0f}</td><td>{median:,.0f}</td></tr>"
            )
        else:
            rows.append(
                f"<tr><td>{_esc(label)}</td>"
                f"<td>{mean:.2f}</td><td>{std:.2f}</td><td>{median:.2f}</td></tr>"
            )
    return f"""
    <table class="stats-table">
      <thead><tr><th>Indicator</th><th>Mean</th><th>Std Dev</th><th>Median</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>"""


def render_pillar_section(
    insight: Dict,
    chart_filename: str,
    section_id: str,
    title: str,
    baseline: Dict,
) -> str:
    """Render a single pillar section."""
    headline = insight.get("headline", "")
    summary = insight.get("executive_summary", "")
    findings = insight.get("key_findings", [])
    risk = insight.get("risk_assessment", "")
    outlook = insight.get("outlook", "")
    risk_cls = _risk_class(risk)

    primary_col = _PILLAR_PRIMARY_COL.get(section_id, "")
    plotly_div = _make_plotly_timeseries(section_id, title, primary_col)
    chart_html = ""
    if plotly_div:
        chart_html = f"""
    <div class="plotly-chart">
      {plotly_div}
      <p class="chart-caption">Source: Portugal Data Intelligence &middot; Data: {START_YEAR}&ndash;{END_YEAR} &middot; Interactive chart — zoom, hover, and download supported</p>
    </div>"""
    else:
        chart_uri = encode_chart(chart_filename)
        if chart_uri:
            chart_html = f"""
    <figure>
      <img src="{chart_uri}" alt="{_esc(title)} chart" loading="lazy">
      <figcaption>Source: Portugal Data Intelligence &middot; Data: {START_YEAR}&ndash;{END_YEAR}</figcaption>
    </figure>"""

    findings_html = ""
    if findings:
        items = "\n".join(f"<li>{_esc(f)}</li>" for f in findings)
        findings_html = f"""
    <h3>Key Findings</h3>
    <ul class="key-findings">{items}</ul>"""

    stats_html = render_stats_table(insight.get("pillar", section_id), baseline)
    stats_section = ""
    if stats_html:
        stats_section = (
            f"<h3>Descriptive Statistics ({START_YEAR}&ndash;{END_YEAR})</h3>{stats_html}"
        )

    risk_html = ""
    if risk:
        risk_html = f"""
    <div class="risk-callout {risk_cls}">
      <strong>Risk Assessment:</strong> {_esc(risk)}
    </div>"""

    outlook_html = ""
    if outlook:
        outlook_html = f"<h3>Outlook</h3>{_paragraphs(outlook)}"

    headline_html = (
        f'  <p style="font-size:1.05rem; font-weight:500; color:var(--navy); margin-bottom:1rem;">'
        f"{_esc(headline)}</p>\n"
        if headline
        else ""
    )
    narrative_html = (
        f'  <div class="pillar-narrative">{_paragraphs(summary)}</div>\n' if summary else ""
    )

    return f"""
<section id="{section_id}" class="pillar-section">
  <h2>{_esc(title)}</h2>
{headline_html}{narrative_html}  {chart_html}
  {findings_html}
  {stats_section}
  {risk_html}
  {outlook_html}
</section>
"""


def render_cross_pillar(briefing: Dict) -> str:
    cross = briefing.get("cross_pillar_insights", {})
    narrative = cross.get("macro_narrative", "")
    relationships = cross.get("relationships", [])

    narrative_html = _paragraphs(narrative) if narrative else ""

    rel_cards = []
    for rel in relationships:
        name = rel.get("name", "")
        desc = rel.get("description", "")
        rel_cards.append(f"""
      <div style="background:#fff; border:1px solid var(--border); border-radius:6px; padding:1rem;">
        <strong style="color:var(--navy);">{_esc(name)}</strong>
        <p style="font-size:0.88rem; margin-top:0.4rem;">{_esc(desc)}</p>
      </div>""")

    rel_grid = ""
    if rel_cards:
        rel_grid = f'<div class="chart-grid">{"".join(rel_cards)}</div>'

    grid_charts = []
    for fn, caption in [
        ("correlation_heatmap.png", "Cross-Pillar Correlation Matrix"),
        ("phillips_curve.png", "Phillips Curve: Unemployment vs Inflation"),
    ]:
        uri = encode_chart(fn)
        if uri:
            grid_charts.append(f"""
      <figure>
        <img src="{uri}" alt="{caption}" loading="lazy">
        <figcaption>{caption}</figcaption>
      </figure>""")

    # Crisis timeline full-width
    crisis_html = ""
    crisis_uri = encode_chart("crisis_timeline.png")
    if crisis_uri:
        crisis_html = f"""
  <figure style="margin-top:2rem;">
    <img src="{crisis_uri}" alt="Crisis Timeline: Macroeconomic Stress Periods" loading="lazy" style="width:100%;">
    <figcaption>Crisis Timeline: Macroeconomic Stress Periods</figcaption>
  </figure>"""

    return f"""
<section id="cross-pillar" class="analysis-section">
  <h2>Cross-Pillar Analysis</h2>
  {narrative_html}
  {rel_grid}
  <div class="chart-grid">
    {"".join(grid_charts)}
  </div>
  {crisis_html}
</section>
"""


def render_benchmarking() -> str:
    charts = []
    for fn, caption in [
        ("benchmark_radar_pt_vs_eu.png", "Portugal vs EU Averages — Radar Comparison"),
        ("benchmark_small_multiples.png", "Peer Country Comparison — Key Indicators"),
    ]:
        uri = encode_chart(fn)
        if uri:
            charts.append(f"""
      <figure>
        <img src="{uri}" alt="{caption}" loading="lazy">
        <figcaption>{caption}</figcaption>
      </figure>""")

    if not charts:
        return ""

    return f"""
<section id="benchmarking" class="analysis-section">
  <h2>EU Benchmarking</h2>
  <p>Portugal's macroeconomic performance compared to key European peers
  (Germany, Spain, France, Italy) and EU/Euro Area averages.</p>
  <div class="chart-grid">
    {"".join(charts)}
  </div>
</section>
"""


def render_regional_section() -> str:
    """Render the NUTS2 regional analysis section with interactive choropleth."""
    from config.settings import DATABASE_PATH
    from src.analysis.regional_analysis import build_choropleth_div, run_regional_analysis

    db_path = str(DATABASE_PATH)
    regional = run_regional_analysis(db_path)
    choropleth_div = (
        build_choropleth_div(db_path, include_plotlyjs=_plotly_include_arg())
        if _HAS_PLOTLY
        else ""
    )

    gdp_block = regional.get("gdp_per_capita_pps", {})
    unemp_block = regional.get("unemployment_rate", {})
    findings = regional.get("key_findings", [])

    findings_html = ""
    if findings:
        items = "".join(f"<li>{_esc(f)}</li>" for f in findings)
        findings_html = f"<ul style='margin:1rem 0 1rem 1.5rem;'>{items}</ul>"

    # Comparison table
    table_rows = ""
    latest_gdp = gdp_block.get("latest_by_region", {})
    latest_unemp = unemp_block.get("latest_by_region", {})
    for code in sorted(latest_gdp.keys()):
        gdp_info = latest_gdp.get(code, {})
        unemp_info = latest_unemp.get(code, {})
        name = gdp_info.get("name", code) if isinstance(gdp_info, dict) else code
        gdp_val = gdp_info.get("value") if isinstance(gdp_info, dict) else gdp_info
        unemp_val = unemp_info.get("value") if isinstance(unemp_info, dict) else unemp_info
        gdp_fmt = f"{gdp_val:,.0f}" if isinstance(gdp_val, (int, float)) else "—"
        unemp_fmt = f"{unemp_val:.1f}%" if isinstance(unemp_val, (int, float)) else "—"
        table_rows += (
            f"<tr><td><strong>{_esc(code)}</strong></td>"
            f"<td>{_esc(name)}</td>"
            f"<td style='text-align:right;'>{gdp_fmt}</td>"
            f"<td style='text-align:right;'>{unemp_fmt}</td></tr>"
        )

    table_html = ""
    if table_rows:
        table_html = f"""
  <table class="stats-table" style="margin-top:1.5rem;">
    <thead>
      <tr>
        <th>Code</th><th>Region</th>
        <th style="text-align:right;">GDP per Capita (PPS)</th>
        <th style="text-align:right;">Unemployment</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>"""

    map_html = ""
    if choropleth_div:
        map_html = f"""
  <div class="plotly-chart" style="margin:1.5rem 0;">
    {choropleth_div}
    <p class="chart-caption">Interactive choropleth — hover over each region for details. Source: Eurostat NUTS2.</p>
  </div>"""

    source_note = ""
    if regional.get("source") == "synthetic_fallback":
        source_note = (
            '<p style="font-size:0.82rem;color:var(--medium-gray);margin-top:1rem;">'
            "<em>Note: data based on synthetic estimates — run <code>python main.py</code> "
            "to populate live data.</em></p>"
        )

    return f"""
<section id="regional" class="analysis-section">
  <h2>Regional Analysis — NUTS2</h2>
  <p>Portugal's macroeconomic performance varies significantly across its seven NUTS2 regions.
  Lisboa accounts for a disproportionate share of national GDP while peripheral regions face
  structural challenges in competitiveness and employment.</p>
  {map_html}
  {table_html}
  {findings_html}
  {source_note}
</section>
"""


def render_executive_dashboard() -> str:
    """Render the executive dashboard overview chart."""
    uri = encode_chart("economic_dashboard.png")
    if not uri:
        return ""
    return f"""
<section id="executive-dashboard" class="analysis-section">
  <h2>Executive Dashboard</h2>
  <p>Single-view summary of all six macroeconomic pillars — GDP, unemployment,
  credit, interest rates, inflation, and public debt — spanning {START_YEAR} to {END_YEAR}.</p>
  <figure>
    <img src="{uri}" alt="Economic Dashboard" loading="lazy">
    <figcaption>Source: Portugal Data Intelligence &middot; Data: {START_YEAR}&ndash;{END_YEAR}</figcaption>
  </figure>
</section>
"""


def render_stl_decomposition() -> str:
    """Render STL seasonal-trend decomposition charts."""
    stl_charts = [
        ("stl_real_gdp.png", "STL Decomposition: Real GDP"),
        ("stl_unemployment_rate.png", "STL Decomposition: Unemployment Rate"),
        ("stl_hicp_inflation.png", "STL Decomposition: HICP Inflation"),
    ]
    charts = []
    for fn, caption in stl_charts:
        uri = encode_chart(fn)
        if uri:
            charts.append(f"""
      <figure>
        <img src="{uri}" alt="{caption}" loading="lazy">
        <figcaption>{caption}</figcaption>
      </figure>""")

    if not charts:
        return ""

    return f"""
<section id="stl-decomposition" class="analysis-section">
  <h2>Seasonal-Trend Decomposition (STL)</h2>
  <p>Decomposition of key economic time series into trend, seasonal, and residual
  components using STL (Seasonal and Trend decomposition using Loess). This reveals
  underlying structural trends stripped of seasonal noise.</p>
  <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:1.5rem;">
    {"".join(charts)}
  </div>
</section>
"""


def render_forecasting() -> str:
    """Render SARIMAX 12-quarter-ahead forecasts with Plotly interactive charts."""
    if not _HAS_PLOTLY:
        return ""

    try:
        from src.analysis.forecasting import Forecaster

        forecasts = Forecaster().generate_all_forecasts()
    except Exception:
        return ""

    if not forecasts:
        return ""

    _PRIMARY_COLS = {
        "gdp": "real_gdp",
        "unemployment": "unemployment_rate",
        "inflation": "hicp",
        "interest_rates": "ecb_main_refinancing_rate",
        "credit": "total_credit",
        "public_debt": "debt_to_gdp_ratio",
    }

    charts_html: list = []

    for pillar, fc_data in forecasts.items():
        if "error" in fc_data:
            continue
        forecast_points = fc_data.get("forecast", [])
        if not forecast_points:
            continue

        indicator = fc_data.get("indicator", pillar.replace("_", " ").title())
        method = fc_data.get("method", "SARIMAX")
        periods = [p["period"] for p in forecast_points]
        central = [p["central"] for p in forecast_points]
        lower_95 = [p["lower_95"] for p in forecast_points]
        upper_95 = [p["upper_95"] for p in forecast_points]
        lower_68 = [p.get("lower_68", p["central"]) for p in forecast_points]
        upper_68 = [p.get("upper_68", p["central"]) for p in forecast_points]

        fig = go.Figure()

        # Historical tail (last 20 observations)
        pcol = _PRIMARY_COLS.get(pillar)
        csv_path = PROCESSED_DATA_DIR / f"{pillar}.csv"
        if pcol and csv_path.exists():
            try:
                hist_df = pd.read_csv(csv_path).tail(20)
                if not hist_df.empty and pcol in hist_df.columns:
                    x_col = "date_key" if "date_key" in hist_df.columns else hist_df.columns[0]
                    fig.add_trace(
                        go.Scatter(
                            x=hist_df[x_col],
                            y=hist_df[pcol],
                            mode="lines",
                            name="Historical",
                            line={"color": "#1A1A2E", "width": 2},
                            hovertemplate="<b>%{x}</b><br>Historical: %{y:.2f}<extra></extra>",
                        )
                    )
            except Exception:
                pass

        # 95% CI band
        fig.add_trace(
            go.Scatter(
                x=periods + periods[::-1],
                y=upper_95 + lower_95[::-1],
                fill="toself",
                fillcolor="rgba(200,16,46,0.08)",
                line={"color": "rgba(255,255,255,0)"},
                name="95% CI",
                hoverinfo="skip",
            )
        )
        # 68% CI band
        fig.add_trace(
            go.Scatter(
                x=periods + periods[::-1],
                y=upper_68 + lower_68[::-1],
                fill="toself",
                fillcolor="rgba(200,16,46,0.15)",
                line={"color": "rgba(255,255,255,0)"},
                name="68% CI",
                hoverinfo="skip",
            )
        )
        # Central forecast
        fig.add_trace(
            go.Scatter(
                x=periods,
                y=central,
                mode="lines+markers",
                name=f"{method} Forecast",
                line={"color": "#C8102E", "width": 2.5, "dash": "dot"},
                marker={"size": 5, "color": "#C8102E"},
                hovertemplate="<b>%{x}</b><br>Forecast: %{y:.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis={"showgrid": True, "gridcolor": "#E8E8E8", "tickangle": -30},
            yaxis={"showgrid": True, "gridcolor": "#E8E8E8"},
            plot_bgcolor="white",
            paper_bgcolor="white",
            font={"family": "Inter, 'Segoe UI', sans-serif", "size": 11},
            margin={"l": 55, "r": 15, "t": 10, "b": 55},
            height=260,
            hovermode="x unified",
            legend={"orientation": "h", "y": -0.28, "x": 0, "font": {"size": 10}},
        )
        try:
            div = pyo.plot(
                fig,
                output_type="div",
                include_plotlyjs=_plotly_include_arg(),
                config={"displayModeBar": True, "displaylogo": False},
            )
            charts_html.append(
                f'<div style="margin-bottom:1.2rem;">'
                f'<h4 style="color:var(--navy);font-size:0.95rem;margin-bottom:0.4rem;">'
                f"{_esc(indicator)}"
                f'<span style="font-size:0.78rem;color:var(--medium-gray);font-weight:400;margin-left:0.5rem;">{method}</span>'
                f"</h4>"
                f'<div class="plotly-chart">{div}</div>'
                f"</div>"
            )
        except Exception:
            continue

    if not charts_html:
        return ""

    # Summary table
    table_rows: list = []
    for pillar, fc_data in forecasts.items():
        fps = fc_data.get("forecast", [])
        if not fps or "error" in fc_data:
            continue
        indicator = fc_data.get("indicator", pillar.title())
        latest = fc_data.get("historical_latest", {})
        lv = latest.get("value")
        last_fc = fps[-1]
        cv = last_fc["central"]
        direction = "▲" if (lv is not None and cv > lv) else "▼"
        dir_color = "#27ae60" if direction == "▲" else "#e74c3c"
        lv_str = f"{lv:.1f}" if lv is not None else "—"
        table_rows.append(
            f"<tr>"
            f"<td><strong>{_esc(indicator)}</strong></td>"
            f"<td style='text-align:center'>{_esc(str(latest.get('period', '—')))}</td>"
            f"<td style='text-align:center'>{lv_str}</td>"
            f"<td style='text-align:center'>{_esc(str(last_fc['period']))}</td>"
            f"<td style='text-align:center'>{cv:.1f}</td>"
            f"<td style='text-align:center;color:{dir_color};font-weight:700'>{direction}</td>"
            f"</tr>"
        )

    table_html = ""
    if table_rows:
        table_html = (
            '<div style="overflow-x:auto;margin-bottom:2rem;">'
            '<table class="stats-table">'
            "<thead><tr>"
            "<th>Indicator</th><th>Latest Period</th><th>Latest Value</th>"
            "<th>Horizon</th><th>Forecast</th><th>Direction</th>"
            "</tr></thead>"
            f'<tbody>{"".join(table_rows)}</tbody>'
            "</table></div>"
        )

    return f"""
<section id="forecasting" class="analysis-section">
  <h2>SARIMAX Forecasting</h2>
  <p>12-quarter-ahead forecasts generated by SARIMAX models with automatic order selection via AIC.
  Models are cached for 7 days (joblib) and refit when new data arrives. Shaded bands show 68%
  and 95% prediction intervals; residual diagnostics include the Ljung-Box test.</p>
  {table_html}
  {"".join(charts_html)}
</section>
"""


def render_risk_matrix(briefing: Dict) -> str:
    risks = briefing.get("risk_matrix", [])
    if not risks:
        return ""

    rows = []
    for r in risks:
        pillar = r.get("pillar", "").replace("_", " ").title()
        level = r.get("risk_level", "moderate")
        desc = r.get("description", "")
        cls = _risk_class(level)
        rows.append(
            f"<tr><td><strong>{_esc(pillar)}</strong></td>"
            f'<td><span class="risk-badge {cls}">{_esc(level)}</span></td>'
            f"<td>{_esc(desc)}</td></tr>"
        )

    return f"""
<section id="risk-matrix" class="analysis-section">
  <h2>Risk Matrix</h2>
  <table class="risk-matrix">
    <thead><tr><th>Pillar</th><th>Risk Level</th><th>Assessment</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>
"""


def render_recommendations(briefing: Dict) -> str:
    recs = briefing.get("strategic_recommendations", [])
    if not recs:
        return ""
    items = "\n".join(f"<li>{_esc(r)}</li>" for r in recs)
    return f"""
<section id="recommendations" class="analysis-section">
  <h2>Strategic Recommendations</h2>
  <ol class="recommendations-list">{items}</ol>
</section>
"""


def render_platform() -> str:
    """Render the Platform & Tools section showcasing v2 capabilities."""
    return f"""
<section id="platform" class="analysis-section">
  <h2>Platform & Tools</h2>
  <p>Portugal Data Intelligence v{VERSION} delivers insights through multiple complementary channels,
  each tailored to a different audience and use case.</p>
  <div class="chart-grid">
    <div style="background:#fff; border:1px solid var(--border); border-radius:6px; padding:1.2rem;">
      <strong style="color:var(--navy);">Interactive Dashboard (Streamlit)</strong>
      <p style="font-size:0.88rem; margin-top:0.5rem;">
        Four-page web dashboard with real-time KPI cards, per-pillar deep-dive with configurable
        year range and indicator filters, cross-pillar correlation heatmap with Phillips curve
        analysis, and a raw data explorer with CSV download.
      </p>
      <p style="font-size:0.8rem; color:var(--medium-gray); margin-top:0.4rem;">
        Launch: <code>streamlit run dashboard/app.py</code>
      </p>
    </div>
    <div style="background:#fff; border:1px solid var(--border); border-radius:6px; padding:1.2rem;">
      <strong style="color:var(--navy);">REST API (FastAPI)</strong>
      <p style="font-size:0.88rem; margin-top:0.5rem;">
        Seven endpoints exposing macroeconomic data programmatically: pillar listing,
        latest values with summary statistics, filtered timeseries queries, active alert
        monitoring, and cross-pillar correlation matrices. Full OpenAPI documentation at <code>/docs</code>.
      </p>
      <p style="font-size:0.8rem; color:var(--medium-gray); margin-top:0.4rem;">
        Launch: <code>uvicorn api.main:app --reload</code>
      </p>
    </div>
    <div style="background:#fff; border:1px solid var(--border); border-radius:6px; padding:1.2rem;">
      <strong style="color:var(--navy);">Ensemble Forecasting</strong>
      <p style="font-size:0.88rem; margin-top:0.5rem;">
        Multi-model forecasting combining SARIMAX, Holt-Winters, linear trend, mean-reversion,
        and log-linear models. Models are automatically weighted by inverse MAE from
        expanding-window backtesting, producing robust consensus projections with 68% and 95%
        confidence bands.
      </p>
    </div>
    <div style="background:#fff; border:1px solid var(--border); border-radius:6px; padding:1.2rem;">
      <strong style="color:var(--navy);">Power BI Dashboard</strong>
      <p style="font-size:0.88rem; margin-top:0.5rem;">
        39 DAX measures across 7 categories (KPIs, YoY growth, moving averages, derived metrics,
        period comparisons, formatting, calculated columns) for enterprise-grade interactive
        dashboards with drill-down and what-if analysis.
      </p>
    </div>
  </div>
  <p style="margin-top:1.2rem; font-size:0.9rem;">
    Additionally, the platform includes a configurable <strong>alert engine</strong> with
    warning/critical thresholds for all six pillars, an <strong>API response cache</strong>
    to reduce redundant HTTP calls to Eurostat, ECB, and Banco de Portugal, and a
    comprehensive <strong>CI/CD pipeline</strong> (GitHub Actions) with linting, testing
    across Python 3.10&ndash;3.12, and automated coverage reporting.
  </p>
</section>
"""


def render_methodology() -> str:
    source_rows = []
    for name, url in DATA_SOURCES.items():
        source_rows.append(f"<tr><td>{_esc(name)}</td><td>{_esc(url)}</td></tr>")

    return f"""
<section id="methodology" class="methodology-section">
  <h2>Methodology & Data Sources</h2>
  <p>This report analyses the Portuguese economy across twelve macroeconomic pillars
  plus regional NUTS2 analysis, using data from {START_YEAR} to {END_YEAR}. All data is
  sourced from authoritative national and European statistical institutions.</p>
  <table class="source-table">
    <thead><tr><th>Source</th><th>URL</th></tr></thead>
    <tbody>{"".join(source_rows)}</tbody>
  </table>
  <p style="margin-top:1rem; font-size:0.85rem; color:var(--medium-gray);">
    <strong>Granularity:</strong> GDP, Public Debt, and External Accounts are quarterly;
    Unemployment, Credit, Interest Rates, and Inflation are monthly; Housing, Labour
    Detail, Fiscal, Inequality, and Regional are annual.<br>
    <strong>Data Quality:</strong> All data passes a 7-layer validation framework
    (schema, nulls, ranges, outliers, drift, consistency, freshness).<br>
    <strong>Analysis Engine:</strong> Python (pandas, statsmodels, scipy) with
    SQLite storage, ensemble forecasting, and automated reporting.<br>
    <strong>Delivery:</strong> Power BI, Streamlit dashboard, self-contained HTML, REST API (FastAPI).<br>
    <strong>Version:</strong> {VERSION} &mdash; Generated {datetime.now().strftime("%d %B %Y")}
  </p>
</section>
"""


def render_footer() -> str:
    generated = datetime.now().strftime("%d %B %Y, %H:%M")
    return f"""
<footer>
  <div class="author">Portugal Data Intelligence v{VERSION}</div>
  <p>Diogo Serino &middot; Portfolio 2026 &middot; Power BI &middot; Streamlit &middot; FastAPI &middot; HTML</p>
  <p style="font-size:0.75rem; color:var(--medium-gray); margin-top:0.25rem;">Report generated: {generated}</p>
</footer>
"""


# =============================================================================
# MAIN GENERATOR
# =============================================================================


def generate_report(output_path: Optional[Path] = None) -> Path:
    """Generate the full HTML report and write to disk."""
    ensure_directories()

    # Reset so plotly.js is embedded exactly once per report (matters when
    # generate_report() is called more than once in the same process).
    _PLOTLY_STATE["included"] = False

    if output_path is None:
        output_path = PROJECT_ROOT / "docs" / "index.html"

    logger.info("Generating HTML report...")

    # Load data
    briefing = load_latest_briefing()
    kpis = load_kpi_values()
    baseline = load_dq_baseline()

    # Build pillar insights lookup
    pillar_insights = {}
    for pi in briefing.get("pillar_insights", []):
        pillar_insights[pi.get("pillar", "")] = pi

    # Render sections
    sections = [
        render_hero(briefing, kpis),
        render_toc(),
        "<main>",
        render_kpi_dashboard(kpis),
    ]

    # Pillar sections
    for key, title, chart_fn, _ in _PILLAR_CONFIG:
        insight = pillar_insights.get(key, {})
        sections.append(render_pillar_section(insight, chart_fn, key, title, baseline))

    # Executive dashboard, cross-pillar, STL, benchmarking, regional, risk, recommendations, platform
    sections.extend(
        [
            render_executive_dashboard(),
            render_cross_pillar(briefing),
            render_stl_decomposition(),
            render_forecasting(),
            render_benchmarking(),
            render_regional_section(),
            render_risk_matrix(briefing),
            render_recommendations(briefing),
            render_platform(),
            render_methodology(),
            "</main>",
            render_footer(),
        ]
    )

    body = "\n".join(sections)

    js_block = """<script>
(function () {
  var bar = document.getElementById("progress-bar");
  var btn = document.getElementById("back-to-top");
  if (!bar || !btn) return;
  window.addEventListener("scroll", function () {
    var h = document.documentElement;
    var pct = h.scrollTop / (h.scrollHeight - h.clientHeight);
    bar.style.width = (Math.min(pct, 1) * 100).toFixed(1) + "%";
    btn.style.display = h.scrollTop > 600 ? "flex" : "none";
  });
  btn.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
})();
</script>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Portugal Macroeconomic Intelligence Briefing</title>
  <style>{CSS}</style>
</head>
<body>
<div id="progress-bar"></div>
<button id="back-to-top" aria-label="Back to top">&#8679;</button>
{body}
{js_block}
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Report generated: %s (%.1f MB)", output_path, size_mb)
    return output_path


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Portugal Economic Intelligence HTML report",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output path (default: docs/index.html)",
    )
    args = parser.parse_args()
    path = generate_report(output_path=args.output)
    print(f"Report ready: {path}")
