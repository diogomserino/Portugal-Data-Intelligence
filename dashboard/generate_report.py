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


def encode_chart(filename: str, max_width: int = 1200) -> str:
    """Read a chart PNG and return a base64 data URI.

    The 300-DPI source charts are large; for the self-contained report we
    downscale the *embedded* copy to a web-friendly width and re-compress it so
    the HTML stays lightweight. The PNGs on disk (used by the README and Power
    BI) are left untouched. Falls back to the raw bytes if Pillow is missing.
    """
    path = CHARTS_DIR / filename
    if not path.exists():
        logger.warning("Chart not found: %s", path)
        return ""
    data = path.read_bytes()
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(data)) as img:
            if img.width > max_width:
                height = round(img.height * max_width / img.width)
                img = img.resize((max_width, height), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            data = buf.getvalue()
    except Exception:  # pragma: no cover - graceful fallback
        pass
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
            mode="lines",
            name=col_label,
            line={"color": "#2251FF", "width": 2.25},
            hovertemplate=f"<b>%{{x}}</b><br>{col_label}: %{{y:.2f}}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis={
            "showgrid": False,
            "tickangle": 0,
            "nticks": 8,
            "linecolor": "#E4E7EB",
            "ticks": "outside",
            "tickcolor": "#E4E7EB",
        },
        yaxis={
            "title": col_label,
            "showgrid": True,
            "gridcolor": "#ECEEF1",
            "zerolinecolor": "#D6DAE0",
        },
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": "Inter, 'Segoe UI', sans-serif", "size": 12, "color": "#3D4754"},
        margin={"l": 60, "r": 12, "t": 12, "b": 40},
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
                "displayModeBar": "hover",
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
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600;700&display=swap');

:root {
  /* Editorial palette: near-black ink, warm grays, one electric-blue accent. */
  --ink: #15191E;
  --ink-soft: #3D4754;
  --gray: #6A737F;
  --gray-faint: #B9BFC7;
  --hairline: #E4E7EB;
  --wash: #F6F7F8;
  --paper: #FFFFFF;
  --accent: #2251FF;
  --accent-dark: #1A3FD6;
  /* Semantic colours: reserved for data (deltas, risk) only. */
  --pos: #0E7C3F;
  --neg: #C03434;
  --warn: #A6690F;
  --risk-low: #0E7C3F;
  --risk-moderate: #A6690F;
  --risk-elevated: #C2410C;
  --risk-high: #B91C1C;
  --serif: 'Source Serif 4', Georgia, 'Times New Roman', serif;
  --sans: 'Inter', 'Segoe UI', -apple-system, sans-serif;
  --font-heading: var(--serif);
  --font-body: var(--sans);
  /* Legacy aliases (used by inline styles in render helpers). */
  --navy: var(--ink);
  --dark-slate: var(--ink-soft);
  --deep-red: var(--neg);
  --forest-green: var(--pos);
  --warm-gold: var(--warn);
  --steel-blue: var(--accent);
  --off-white: var(--paper);
  --light-gray: var(--wash);
  --border: var(--hairline);
  --medium-gray: var(--gray);
  --max-width: 1100px;
  --prose: 740px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: var(--font-body);
  font-size: 16px;
  line-height: 1.7;
  color: var(--ink-soft);
  background: var(--paper);
}

::selection { background: rgba(34, 81, 255, 0.14); }

/* --- EDITORIAL COVER --- */
.cover {
  background: var(--paper);
  padding: 4.5rem 2.5rem 3rem;
  border-bottom: 1px solid var(--hairline);
}
.cover-inner { max-width: 940px; margin: 0 auto; }
.kicker {
  font-family: var(--sans);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 1.5rem;
}
.cover h1 {
  font-family: var(--serif);
  font-size: 3.3rem;
  font-weight: 700;
  line-height: 1.12;
  letter-spacing: -0.015em;
  color: var(--ink);
  max-width: 21ch;
}
.cover .dek {
  font-family: var(--serif);
  font-size: 1.25rem;
  line-height: 1.55;
  color: var(--ink-soft);
  margin-top: 1.1rem;
  max-width: 52ch;
}
.cover .meta-row {
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--gray);
  margin: 1.6rem 0 2.5rem;
}
.cover .meta-row span + span::before { content: "·"; margin: 0 0.6rem; color: var(--gray-faint); }

/* KPI ticker strip */
.ticker {
  display: flex;
  flex-wrap: wrap;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--hairline);
}
.ticker-item {
  display: flex;
  align-items: baseline;
  gap: 0.55rem;
  padding: 0.95rem 1.5rem 0.95rem 0;
  margin-right: 1.5rem;
  border-right: 1px solid var(--hairline);
}
.ticker-item:last-child { border-right: none; margin-right: 0; }
.t-label {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--gray);
}
.t-value {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.t-delta { font-size: 0.72rem; font-weight: 600; }
.t-delta.positive { color: var(--pos); }
.t-delta.negative { color: var(--neg); }
.t-delta.moderate { color: var(--warn); }
.t-delta.neutral { color: var(--gray); }

/* Executive summary panel */
.exec-panel {
  max-width: 940px;
  margin: 2.5rem auto 0;
  padding: 1.8rem 2.2rem;
  background: var(--wash);
  border-left: 3px solid var(--accent);
}
.exec-panel .panel-label {
  font-family: var(--sans);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink);
  margin-bottom: 0.9rem;
}
.exec-panel p {
  font-size: 0.97rem;
  line-height: 1.75;
  color: var(--ink-soft);
  margin-bottom: 0.8rem;
}
.exec-panel p:last-child { margin-bottom: 0; }

/* --- LAYOUT SHELL: sticky rail + content column --- */
.layout {
  max-width: 1340px;
  margin: 0 auto;
  padding: 0 2.5rem;
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  column-gap: 4.5rem;
}
.content { min-width: 0; max-width: 980px; }

#side-rail {
  position: sticky;
  top: 0;
  align-self: start;
  max-height: 100vh;
  overflow-y: auto;
  padding: 3rem 0 2rem;
  scrollbar-width: thin;
}
#side-rail .rail-title {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink);
  margin-bottom: 1rem;
}
#side-rail ol { list-style: none; counter-reset: rail; }
#side-rail li { counter-increment: rail; }
#side-rail a {
  display: flex;
  gap: 0.6rem;
  padding: 0.3rem 0.75rem;
  font-size: 0.78rem;
  line-height: 1.45;
  color: var(--gray);
  text-decoration: none;
  border-left: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
#side-rail a::before {
  content: counter(rail, decimal-leading-zero);
  font-size: 0.66rem;
  font-weight: 600;
  color: var(--gray-faint);
  font-variant-numeric: tabular-nums;
  padding-top: 0.12rem;
}
#side-rail a:hover { color: var(--ink); }
#side-rail li.active a {
  color: var(--accent);
  border-left-color: var(--accent);
  font-weight: 600;
}
#side-rail li.active a::before { color: var(--accent); }

/* --- MOBILE CONTENTS (rail hidden on narrow screens) --- */
.toc-mobile {
  display: none;
  margin: 2rem 0;
  padding: 1.25rem 1.5rem;
  background: var(--wash);
  border: 1px solid var(--hairline);
}
.toc-mobile summary {
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink);
  cursor: pointer;
}
.toc-mobile a {
  display: block;
  padding: 0.25rem 0;
  font-size: 0.85rem;
  color: var(--ink-soft);
  text-decoration: none;
}
.toc-mobile a:hover { color: var(--accent); }

/* --- MAIN CONTENT --- */
main { counter-reset: sec exhibit; }
main > section {
  counter-increment: sec;
  padding: 3.25rem 0;
  border-top: 1px solid var(--hairline);
  margin: 0;
}
main > section:first-child { border-top: none; padding-top: 2.75rem; }

main > section > h2 {
  font-family: var(--serif);
  font-size: 1.9rem;
  font-weight: 600;
  line-height: 1.22;
  letter-spacing: -0.01em;
  color: var(--ink);
  margin-bottom: 1.25rem;
  border: none;
  padding: 0;
}
main > section > h2::before {
  content: "Section " counter(sec, decimal-leading-zero);
  display: block;
  font-family: var(--sans);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.8rem;
}

/* Standfirst (pillar headline) */
.standfirst {
  font-family: var(--serif);
  font-size: 1.22rem;
  line-height: 1.5;
  color: var(--ink);
  margin-bottom: 1.4rem;
  max-width: var(--prose);
}

section h3 {
  font-family: var(--sans);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink);
  margin: 2rem 0 0.8rem;
}

/* Constrain prose for readability; exhibits and tables run wider. */
main section p { max-width: var(--prose); }
.pillar-narrative { margin-bottom: 1.5rem; white-space: pre-line; max-width: var(--prose); }
.pillar-narrative p { margin-bottom: 0.85rem; }

/* --- KPI DASHBOARD --- */
.kpi-dashboard h2 { margin-bottom: 1.5rem; }
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--hairline);
  border: 1px solid var(--hairline);
}
.kpi-card {
  background: var(--paper);
  padding: 1.3rem 1.5rem 1.2rem;
  text-align: left;
}
.kpi-label {
  font-size: 0.67rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gray);
}
.kpi-value {
  font-size: 2.1rem;
  font-weight: 600;
  line-height: 1.15;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
  margin-top: 0.35rem;
}
.kpi-meta {
  display: flex;
  gap: 0.85rem;
  align-items: baseline;
  margin-top: 0.45rem;
  font-size: 0.74rem;
  color: var(--gray);
}
.kpi-period { font-variant-numeric: tabular-nums; }
.kpi-trend { font-weight: 600; }
.kpi-trend.positive { color: var(--pos); }
.kpi-trend.moderate { color: var(--warn); }
.kpi-trend.negative { color: var(--neg); }
.kpi-trend.neutral { color: var(--gray); }

/* --- EXHIBIT SYSTEM (numbered figures) --- */
.exhibit {
  counter-increment: exhibit;
  margin: 2.25rem 0;
  text-align: left;
}
.exhibit-head {
  display: block;
  font-family: var(--sans);
  font-size: 0.92rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--ink);
  padding-bottom: 0.55rem;
  border-bottom: 1px solid var(--ink);
  margin-bottom: 1rem;
  font-style: normal;
  text-align: left;
}
.exhibit-head::before {
  content: "Exhibit " counter(exhibit);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin-right: 0.9rem;
}
.exhibit img {
  max-width: 100%;
  height: auto;
  border: none;
  border-radius: 0;
}
.exhibit-source {
  font-size: 0.74rem;
  line-height: 1.5;
  color: var(--gray);
  margin-top: 0.6rem;
  max-width: none !important;
}

figure { margin: 1.5rem 0; }
figure img { max-width: 100%; height: auto; }
figcaption { font-size: 0.78rem; color: var(--gray); margin-top: 0.5rem; }

/* Findings list */
.key-findings { margin: 1rem 0; padding-left: 1.1rem; max-width: var(--prose); }
.key-findings li {
  margin-bottom: 0.5rem;
  font-size: 0.92rem;
  line-height: 1.65;
}
.key-findings li::marker { color: var(--accent); }

/* Risk callout */
.risk-callout {
  padding: 1.1rem 1.4rem;
  background: var(--wash);
  border-left: 3px solid var(--gray);
  margin: 1.5rem 0;
  font-size: 0.91rem;
  max-width: var(--prose);
}
.risk-callout.low { border-left-color: var(--risk-low); }
.risk-callout.moderate { border-left-color: var(--risk-moderate); }
.risk-callout.elevated { border-left-color: var(--risk-elevated); }
.risk-callout.high { border-left-color: var(--risk-high); }
.risk-callout strong { color: var(--ink); }

/* Stats table */
.stats-table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.88rem;
  font-variant-numeric: tabular-nums;
}
.stats-table th {
  background: none;
  color: var(--gray);
  font-size: 0.69rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-align: left;
  padding: 0.55rem 0.8rem 0.55rem 0;
  border-bottom: 2px solid var(--ink);
}
.stats-table th:not(:first-child) { text-align: right; }
.stats-table td {
  padding: 0.55rem 0.8rem 0.55rem 0;
  border-bottom: 1px solid var(--hairline);
  color: var(--ink-soft);
}
.stats-table td:first-child { color: var(--ink); }
.stats-table td:not(:first-child) { text-align: right; }

/* --- ANALYSIS SECTIONS --- */
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
  margin: 1.5rem 0;
}
.plotly-chart { margin: 0; border: none; border-radius: 0; overflow: hidden; }
.plotly-chart .chart-caption {
  font-size: 0.74rem;
  color: var(--gray);
  text-align: left;
  padding: 0.5rem 0 0;
  background: none;
}

/* Info cards (cross-pillar relationships, platform) */
.info-card {
  background: var(--paper);
  border: 1px solid var(--hairline);
  padding: 1.2rem 1.4rem;
}
.info-card strong { color: var(--ink); font-size: 0.95rem; }
.info-card p { font-size: 0.87rem; margin-top: 0.45rem; max-width: none; }
.info-card .launch { font-size: 0.78rem; color: var(--gray); margin-top: 0.5rem; }
.info-card code { font-size: 0.78rem; background: var(--wash); padding: 0.1rem 0.35rem; }

/* --- RISK MATRIX --- */
.risk-matrix {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.9rem;
}
.risk-matrix th {
  background: none;
  color: var(--gray);
  font-size: 0.69rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.55rem 1rem 0.55rem 0;
  text-align: left;
  border-bottom: 2px solid var(--ink);
}
.risk-matrix td {
  padding: 0.7rem 1rem 0.7rem 0;
  border-bottom: 1px solid var(--hairline);
  vertical-align: top;
}
.risk-badge {
  display: inline-block;
  padding: 0.18rem 0.6rem;
  border-radius: 3px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}
.risk-badge.low { background: rgba(14, 124, 63, 0.1); color: var(--risk-low); }
.risk-badge.moderate { background: rgba(166, 105, 15, 0.12); color: var(--risk-moderate); }
.risk-badge.elevated { background: rgba(194, 65, 12, 0.1); color: var(--risk-elevated); }
.risk-badge.high { background: rgba(185, 28, 28, 0.1); color: var(--risk-high); }

/* --- RECOMMENDATIONS --- */
.recommendations-list {
  counter-reset: rec;
  list-style: none;
  padding: 0;
  max-width: var(--prose);
}
.recommendations-list li {
  counter-increment: rec;
  padding: 1.1rem 0 1.1rem 3.2rem;
  border-bottom: 1px solid var(--hairline);
  position: relative;
  font-size: 0.94rem;
  line-height: 1.7;
}
.recommendations-list li::before {
  content: counter(rec, decimal-leading-zero);
  position: absolute;
  left: 0;
  top: 1.15rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}

/* --- METHODOLOGY --- */
.methodology-section {
  background: var(--wash);
  padding: 2.5rem 2.5rem 2.25rem !important;
  margin: 3rem 0 0 !important;
}
.source-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  margin: 1rem 0;
}
.source-table th, .source-table td {
  padding: 0.5rem 0.8rem 0.5rem 0;
  border-bottom: 1px solid var(--hairline);
  text-align: left;
}
.source-table th {
  font-size: 0.69rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--gray);
  border-bottom: 2px solid var(--ink);
}

/* --- FOOTER --- */
footer {
  max-width: 1340px;
  margin: 0 auto;
  padding: 2rem 2.5rem 3rem;
  border-top: 2px solid var(--ink);
  font-size: 0.8rem;
  color: var(--gray);
  text-align: left;
}
footer .author { font-weight: 600; color: var(--ink); font-size: 0.9rem; }

/* --- SCROLL PROGRESS BAR --- */
#progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  height: 2px;
  width: 0%;
  background: var(--accent);
  z-index: 9999;
  transition: width 0.05s linear;
  pointer-events: none;
}

/* --- BACK TO TOP BUTTON --- */
#back-to-top {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  width: 2.6rem;
  height: 2.6rem;
  background: var(--paper);
  color: var(--ink);
  border: 1px solid var(--hairline);
  border-radius: 50%;
  cursor: pointer;
  display: none;
  align-items: center;
  justify-content: center;
  font-size: 1.05rem;
  font-weight: 700;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
  z-index: 9998;
  transition: color 0.2s, border-color 0.2s;
  line-height: 1;
}
#back-to-top:hover { color: var(--accent); border-color: var(--accent); }

/* --- RESPONSIVE --- */
@media (max-width: 1080px) {
  .layout { display: block; padding: 0 1.5rem; }
  #side-rail { display: none; }
  .toc-mobile { display: block; }
  .content { max-width: none; }
}
@media (max-width: 768px) {
  .cover { padding: 3rem 1.5rem 2rem; }
  .cover h1 { font-size: 2.2rem; }
  .cover .dek { font-size: 1.05rem; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .chart-grid { grid-template-columns: 1fr !important; }
  .ticker-item { padding-right: 1rem; margin-right: 1rem; }
  main > section > h2 { font-size: 1.5rem; }
}
@media (max-width: 480px) {
  .cover h1 { font-size: 1.75rem; }
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .kpi-value { font-size: 1.6rem; }
  #back-to-top { bottom: 1rem; right: 1rem; width: 2.25rem; height: 2.25rem; font-size: 0.95rem; }
}

/* --- PRINT --- */
@media print {
  #side-rail, .toc-mobile, #progress-bar, #back-to-top { display: none !important; }
  .layout { display: block; padding: 0; }
  .cover { padding: 2rem 0 1.5rem; }
  main > section { page-break-inside: avoid; padding: 1.5rem 0; }
  body { font-size: 10.5pt; }
  .exhibit-head, main > section > h2::before { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
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
    """Editorial cover: kicker, serif headline, dek, meta row, KPI ticker, summary panel."""
    title = briefing.get("title", "Portugal Macroeconomic Intelligence Briefing")
    date = briefing.get("date", datetime.now().strftime("%d %B %Y"))
    summary = briefing.get("overall_assessment", "")

    # KPI ticker strip
    ticker_html = ""
    if kpis:
        items = []
        _TICKER_DEFS = [
            ("gdp", "gdp_growth_yoy", "GDP", ".1f", "%"),
            ("unemployment", "unemployment_rate", "Unemployment", ".1f", "%"),
            ("inflation", "hicp", "Inflation", ".1f", "%"),
            ("public_debt", "debt_to_gdp_ratio", "Debt/GDP", ".1f", "%"),
            ("interest_rates", "portugal_10y_bond_yield", "10Y Yield", ".2f", "%"),
        ]
        for pk, col, lbl, fmt, suf in _TICKER_DEFS:
            val = kpis.get(pk, {}).get(col)
            if val is None:
                continue
            arrow, trend_cls = _kpi_trend(pk, col)
            delta = f'<span class="t-delta {trend_cls}">{arrow}</span>' if arrow else ""
            items.append(
                f'<div class="ticker-item">'
                f'<span class="t-label">{lbl}</span>'
                f'<span class="t-value">{val:{fmt}}{suf}</span>'
                f"{delta}"
                f"</div>"
            )
        if items:
            ticker_html = f'<div class="ticker">{"".join(items)}</div>'

    summary_html = ""
    if summary:
        summary_html = f"""
  <div class="exec-panel">
    <p class="panel-label">Executive summary</p>
    {_paragraphs(summary)}
  </div>"""

    return f"""
<header class="cover">
  <div class="cover-inner">
    <p class="kicker">Economic Research &middot; Portugal Data Intelligence</p>
    <h1>{_esc(title)}</h1>
    <p class="dek">A structural read of the Portuguese economy across twelve
    macroeconomic pillars, {START_YEAR}&ndash;{END_YEAR}.</p>
    <p class="meta-row"><span>{_esc(date)}</span><span>Edition v{VERSION}</span><span>Diogo Serino</span></p>
    {ticker_html}
    {summary_html}
  </div>
</header>
"""


def _toc_entries() -> list:
    """Ordered (anchor, label) pairs matching the document section order."""
    entries = [("key-indicators", "Key Indicators")]
    for key, title, _, _icon in _PILLAR_CONFIG:
        entries.append((key, title))
    entries.extend(
        [
            ("executive-dashboard", "Executive Dashboard"),
            ("cross-pillar", "Cross-Pillar Analysis"),
            ("stl-decomposition", "STL Decomposition"),
            ("forecasting", "SARIMAX Forecasting"),
            ("benchmarking", "EU Benchmarking"),
            ("regional", "Regional Analysis (NUTS2)"),
            ("risk-matrix", "Risk Matrix"),
            ("recommendations", "Strategic Recommendations"),
            ("platform", "Platform &amp; Tools"),
            ("methodology", "Methodology"),
        ]
    )
    return entries


def render_side_rail() -> str:
    """Sticky left-rail contents with numbered entries (desktop)."""
    items = "\n    ".join(
        f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in _toc_entries()
    )
    return f"""
<aside id="side-rail" aria-label="Contents">
  <p class="rail-title">Contents</p>
  <ol>
    {items}
  </ol>
</aside>
"""


def render_toc() -> str:
    """Collapsible contents block shown on narrow screens (rail hidden)."""
    items = "\n    ".join(f'<a href="#{anchor}">{label}</a>' for anchor, label in _toc_entries())
    return f"""
<details class="toc-mobile">
  <summary>Contents</summary>
  <div style="margin-top:0.75rem;">
    {items}
  </div>
</details>
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
                f'<span class="kpi-trend {trend_cls}">{arrow} vs prev</span>' if arrow else ""
            )
        else:
            formatted = "N/A"
            sem_cls = "neutral"
            trend_html = ""
        cards.append(
            f'<div class="kpi-card {sem_cls}">'
            f'<div class="kpi-label">{_esc(label)}</div>'
            f'<div class="kpi-value">{formatted}</div>'
            f'<div class="kpi-meta"><span class="kpi-period">{_esc(period)}</span>{trend_html}</div>'
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


_DEFAULT_SOURCE = "INE &middot; Banco de Portugal &middot; Eurostat &middot; ECB"


def _exhibit(inner_html: str, title: str, source: str = _DEFAULT_SOURCE, note: str = "") -> str:
    """Wrap a chart in the numbered-exhibit pattern: title above, source below."""
    note_html = f" &mdash; {note}" if note else ""
    return f"""
    <figure class="exhibit">
      <figcaption class="exhibit-head">{title}</figcaption>
      {inner_html}
      <p class="exhibit-source">Source: {source}{note_html}</p>
    </figure>"""


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
    col_label = _COLUMN_LABELS.get(primary_col, primary_col.replace("_", " ").title())
    exhibit_title = f"{col_label}, {START_YEAR}&ndash;{END_YEAR}"
    chart_html = ""
    if plotly_div:
        chart_html = _exhibit(
            f'<div class="plotly-chart">{plotly_div}</div>',
            exhibit_title,
            note="interactive: zoom, hover, download",
        )
    else:
        chart_uri = encode_chart(chart_filename)
        if chart_uri:
            chart_html = _exhibit(
                f'<img src="{chart_uri}" alt="{_esc(title)} chart" loading="lazy">',
                exhibit_title,
            )

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

    headline_html = f'  <p class="standfirst">{_esc(headline)}</p>\n' if headline else ""
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
      <div class="info-card">
        <strong>{_esc(name)}</strong>
        <p>{_esc(desc)}</p>
      </div>""")

    rel_grid = ""
    if rel_cards:
        rel_grid = f'<div class="chart-grid">{"".join(rel_cards)}</div>'

    grid_charts = []
    for fn, caption in [
        ("correlation_heatmap.png", "Cross-pillar correlation matrix"),
        ("phillips_curve.png", "Phillips curve: unemployment vs inflation"),
    ]:
        uri = encode_chart(fn)
        if uri:
            grid_charts.append(
                _exhibit(f'<img src="{uri}" alt="{caption}" loading="lazy">', caption)
            )

    # Crisis timeline full-width
    crisis_html = ""
    crisis_uri = encode_chart("crisis_timeline.png")
    if crisis_uri:
        crisis_html = _exhibit(
            f'<img src="{crisis_uri}" alt="Crisis timeline" loading="lazy" style="width:100%;">',
            "Crisis timeline: macroeconomic stress periods",
        )

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
        ("benchmark_radar_pt_vs_eu.png", "Portugal vs EU averages — normalised radar"),
        ("benchmark_small_multiples.png", "Peer country comparison — key indicators"),
    ]:
        uri = encode_chart(fn)
        if uri:
            charts.append(_exhibit(f'<img src="{uri}" alt="{caption}" loading="lazy">', caption))

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
        build_choropleth_div(db_path, include_plotlyjs=_plotly_include_arg()) if _HAS_PLOTLY else ""
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
        map_html = _exhibit(
            f'<div class="plotly-chart">{choropleth_div}</div>',
            "GDP per capita by NUTS2 region (PPS), latest year",
            source="Eurostat (nama_10r_2gdp)",
            note="interactive choropleth — hover over each region",
        )

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
    dashboard_exhibit = _exhibit(
        f'<img src="{uri}" alt="Economic Dashboard" loading="lazy">',
        f"Six core pillars at a glance, {START_YEAR}&ndash;{END_YEAR}",
    )
    return f"""
<section id="executive-dashboard" class="analysis-section">
  <h2>Executive Dashboard</h2>
  <p>Single-view summary of all six macroeconomic pillars — GDP, unemployment,
  credit, interest rates, inflation, and public debt — spanning {START_YEAR} to {END_YEAR}.</p>
  {dashboard_exhibit}
</section>
"""


def render_stl_decomposition() -> str:
    """Render STL seasonal-trend decomposition charts."""
    stl_charts = [
        ("stl_real_gdp.png", "STL decomposition: real GDP"),
        ("stl_unemployment_rate.png", "STL decomposition: unemployment rate"),
        ("stl_hicp_inflation.png", "STL decomposition: HICP inflation"),
    ]
    charts = []
    for fn, caption in stl_charts:
        uri = encode_chart(fn)
        if uri:
            charts.append(_exhibit(f'<img src="{uri}" alt="{caption}" loading="lazy">', caption))

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
                fillcolor="rgba(34,81,255,0.07)",
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
                fillcolor="rgba(34,81,255,0.13)",
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
                mode="lines",
                name=f"{method} Forecast",
                line={"color": "#2251FF", "width": 2.25, "dash": "dot"},
                hovertemplate="<b>%{x}</b><br>Forecast: %{y:.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis={
                "showgrid": False,
                "tickangle": 0,
                "nticks": 8,
                "linecolor": "#E4E7EB",
                "ticks": "outside",
                "tickcolor": "#E4E7EB",
            },
            yaxis={"showgrid": True, "gridcolor": "#ECEEF1"},
            plot_bgcolor="white",
            paper_bgcolor="white",
            font={"family": "Inter, 'Segoe UI', sans-serif", "size": 11, "color": "#3D4754"},
            margin={"l": 55, "r": 12, "t": 8, "b": 45},
            height=260,
            hovermode="x unified",
            legend={"orientation": "h", "y": -0.28, "x": 0, "font": {"size": 10}},
        )
        try:
            div = pyo.plot(
                fig,
                output_type="div",
                include_plotlyjs=_plotly_include_arg(),
                config={"displayModeBar": "hover", "displaylogo": False},
            )
            charts_html.append(
                _exhibit(
                    f'<div class="plotly-chart">{div}</div>',
                    f"{_esc(indicator)} — 12-quarter forecast",
                    source="Portugal Data Intelligence model suite",
                    note=f"method: {method}; shaded bands are 68% / 95% intervals",
                )
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
        dir_color = "#0E7C3F" if direction == "▲" else "#C03434"
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
    <div class="info-card">
      <strong>Interactive Dashboard (Streamlit)</strong>
      <p>
        Four-page web dashboard with real-time KPI cards, per-pillar deep-dive with configurable
        year range and indicator filters, cross-pillar correlation heatmap with Phillips curve
        analysis, and a raw data explorer with CSV download.
      </p>
      <p class="launch">Launch: <code>streamlit run dashboard/app.py</code></p>
    </div>
    <div class="info-card">
      <strong>REST API (FastAPI)</strong>
      <p>
        Seven endpoints exposing macroeconomic data programmatically: pillar listing,
        latest values with summary statistics, filtered timeseries queries, active alert
        monitoring, and cross-pillar correlation matrices. Full OpenAPI documentation at <code>/docs</code>.
      </p>
      <p class="launch">Launch: <code>uvicorn api.main:app --reload</code></p>
    </div>
    <div class="info-card">
      <strong>Ensemble Forecasting</strong>
      <p>
        Multi-model forecasting combining SARIMAX, Holt-Winters, linear trend, mean-reversion,
        and log-linear models. Models are automatically weighted by inverse MAE from
        expanding-window backtesting, producing robust consensus projections with 68% and 95%
        confidence bands.
      </p>
    </div>
    <div class="info-card">
      <strong>Power BI Dashboard</strong>
      <p>
        39 DAX measures across 7 categories (KPIs, YoY growth, moving averages, derived metrics,
        period comparisons, formatting, calculated columns) for enterprise-grade interactive
        dashboards with drill-down and what-if analysis.
      </p>
    </div>
  </div>
  <p style="margin-top:1.2rem; font-size:0.9rem;">
    Additionally, the platform includes a configurable <strong>alert engine</strong> with
    warning/critical thresholds for 11 indicators across the economic pillars, an <strong>API response cache</strong>
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
  plus regional NUTS2 analysis, using data from {START_YEAR} to {END_YEAR}. The core
  macro-financial pillars (GDP, unemployment, inflation, interest rates, credit,
  public debt) and the inequality and regional series carry the official values
  published by the institutions below. The housing, labour-structure, external-accounts
  and fiscal pillars are modelled series calibrated to the corresponding official
  releases (Eurostat, INE, Banco de Portugal); they track the published levels and
  dynamics but are not the raw official records.</p>
  <table class="source-table">
    <thead><tr><th>Source</th><th>URL</th></tr></thead>
    <tbody>{"".join(source_rows)}</tbody>
  </table>
  <p style="margin-top:1rem; font-size:0.85rem; color:var(--medium-gray);">
    <strong>Granularity:</strong> GDP, Public Debt, and External Accounts are quarterly;
    Unemployment, Credit, Interest Rates, and Inflation are monthly; Housing, Labour
    Detail, Fiscal, Inequality, and Regional are annual.<br>
    <strong>Data Quality:</strong> All pillars pass an 8-check validation framework
    (schema, nulls, ranges, outliers, drift, completeness, consistency, freshness).<br>
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

    # Render sections: editorial cover, then a two-column shell with a sticky
    # contents rail (desktop) and the content column.
    sections = [
        render_hero(briefing, kpis),
        '<div class="layout">',
        render_side_rail(),
        '<div class="content">',
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
            "</div>",
            "</div>",
            render_footer(),
        ]
    )

    body = "\n".join(sections)

    js_block = """<script>
(function () {
  var bar = document.getElementById("progress-bar");
  var btn = document.getElementById("back-to-top");
  if (bar && btn) {
    window.addEventListener("scroll", function () {
      var h = document.documentElement;
      var pct = h.scrollTop / (h.scrollHeight - h.clientHeight);
      bar.style.width = (Math.min(pct, 1) * 100).toFixed(1) + "%";
      btn.style.display = h.scrollTop > 600 ? "flex" : "none";
    });
    btn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // Scroll-spy: highlight the contents-rail entry for the section in view.
  var links = document.querySelectorAll("#side-rail a[href^='#']");
  if (!links.length) return;
  var byId = {};
  links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a.parentElement; });
  var sections = Array.prototype.slice
    .call(document.querySelectorAll("main > section[id]"))
    .filter(function (s) { return byId[s.id]; });
  var current = null;
  function spy() {
    var y = window.scrollY + 140;
    var active = sections[0];
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].offsetTop <= y) active = sections[i];
    }
    if (!active || active === current) return;
    current = active;
    links.forEach(function (a) { a.parentElement.classList.remove("active"); });
    var li = byId[active.id];
    li.classList.add("active");
    if (li.scrollIntoView) li.scrollIntoView({ block: "nearest" });
  }
  window.addEventListener("scroll", spy, { passive: true });
  spy();
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
