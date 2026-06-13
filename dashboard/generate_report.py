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
from src.reporting.i18n import (
    COLUMN_LABELS,
    DEFAULT_LANG,
    FORECAST_INDICATORS,
    LANG_FULL,
    LANG_NAMES,
    PILLAR_TITLES,
    SUPPORTED_LANGS,
    tr,
)
from src.utils.logger import get_logger

logger = get_logger("generate_report")

# Human-readable column labels now live in src/reporting/i18n.py (bilingual).
# This alias keeps the English set available for any language-agnostic caller.
_COLUMN_LABELS = COLUMN_LABELS["en"]


def _col_label(col: str, lang: str = DEFAULT_LANG) -> str:
    """Localised, human-readable label for an indicator column."""
    return COLUMN_LABELS.get(lang, COLUMN_LABELS[DEFAULT_LANG]).get(
        col, col.replace("_", " ").title()
    )


# Output filename per language (English keeps the canonical docs/index.html).
_OUTPUT_NAME = {"en": "index.html", "pt": "index.pt.html"}


def _output_for_lang(lang: str) -> Path:
    return PROJECT_ROOT / "docs" / _OUTPUT_NAME.get(lang, "index.html")


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


def load_latest_briefing(lang: str = DEFAULT_LANG) -> Dict[str, Any]:
    """Load the most recent executive briefing JSON for the given language.

    Portuguese briefings are written as ``executive_briefing_pt_*.json`` and
    English ones keep the canonical ``executive_briefing_*.json`` name; the
    English glob therefore excludes the ``pt`` files it would otherwise match.
    """
    if lang == "pt":
        files = sorted(INSIGHTS_DIR.glob("executive_briefing_pt_*.json"))
    else:
        files = sorted(
            p
            for p in INSIGHTS_DIR.glob("executive_briefing_*.json")
            if not p.name.startswith("executive_briefing_pt_")
        )
    if not files:
        logger.warning("No %s executive briefing found in %s", lang, INSIGHTS_DIR)
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


def _make_plotly_timeseries(
    pillar_key: str, title: str, primary_col: str, lang: str = DEFAULT_LANG
) -> str:
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
    col_label = _col_label(primary_col, lang)

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

/* --- LANGUAGE SWITCH --- */
#lang-switch {
  position: fixed;
  top: 0.85rem;
  right: 1rem;
  display: flex;
  gap: 1px;
  background: var(--hairline);
  border: 1px solid var(--hairline);
  border-radius: 4px;
  overflow: hidden;
  z-index: 9998;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
}
#lang-switch a {
  display: block;
  padding: 0.3rem 0.6rem;
  font-family: var(--sans);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-decoration: none;
  color: var(--gray);
  background: var(--paper);
}
#lang-switch a:hover { color: var(--ink); }
#lang-switch a.active { background: var(--accent); color: #fff; }

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
  #side-rail, .toc-mobile, #progress-bar, #back-to-top, #lang-switch { display: none !important; }
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


def render_hero(briefing: Dict, kpis: Optional[Dict] = None, lang: str = DEFAULT_LANG) -> str:
    """Editorial cover: kicker, serif headline, dek, meta row, KPI ticker, summary panel."""
    S = tr(lang)
    title = briefing.get("title", S["default_briefing_title"])
    date = briefing.get("date", datetime.now().strftime("%d %B %Y"))
    summary = briefing.get("overall_assessment", "")

    # KPI ticker strip
    ticker_html = ""
    if kpis:
        items = []
        _TICKER_DEFS = [
            ("gdp", "gdp_growth_yoy", S["ticker_gdp"], ".1f", "%"),
            ("unemployment", "unemployment_rate", S["ticker_unemployment"], ".1f", "%"),
            ("inflation", "hicp", S["ticker_inflation"], ".1f", "%"),
            ("public_debt", "debt_to_gdp_ratio", S["ticker_debt"], ".1f", "%"),
            ("interest_rates", "portugal_10y_bond_yield", S["ticker_yield"], ".2f", "%"),
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
    <p class="panel-label">{S["exec_summary_label"]}</p>
    {_paragraphs(summary)}
  </div>"""

    return f"""
<header class="cover">
  <div class="cover-inner">
    <p class="kicker">{S["kicker"]}</p>
    <h1>{_esc(title)}</h1>
    <p class="dek">{S["dek"].format(start=START_YEAR, end=END_YEAR)}</p>
    <p class="meta-row"><span>{_esc(date)}</span><span>{S["edition"].format(version=VERSION)}</span><span>Diogo Serino</span></p>
    {ticker_html}
    {summary_html}
  </div>
</header>
"""


def _toc_entries(lang: str = DEFAULT_LANG) -> list:
    """Ordered (anchor, label) pairs matching the document section order."""
    S = tr(lang)
    entries = [("key-indicators", S["toc_key_indicators"])]
    for key, title, _, _icon in _PILLAR_CONFIG:
        entries.append((key, PILLAR_TITLES.get(lang, PILLAR_TITLES[DEFAULT_LANG]).get(key, title)))
    entries.extend(
        [
            ("executive-dashboard", S["toc_executive_dashboard"]),
            ("cross-pillar", S["toc_cross_pillar"]),
            ("stl-decomposition", S["toc_stl"]),
            ("forecasting", S["toc_forecasting"]),
            ("benchmarking", S["toc_benchmarking"]),
            ("regional", S["toc_regional"]),
            ("risk-matrix", S["toc_risk_matrix"]),
            ("recommendations", S["toc_recommendations"]),
            ("platform", S["toc_platform"]),
            ("methodology", S["toc_methodology"]),
        ]
    )
    return entries


def render_side_rail(lang: str = DEFAULT_LANG) -> str:
    """Sticky left-rail contents with numbered entries (desktop)."""
    items = "\n    ".join(
        f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in _toc_entries(lang)
    )
    return f"""
<aside id="side-rail" aria-label="{tr(lang)["contents"]}">
  <p class="rail-title">{tr(lang)["contents"]}</p>
  <ol>
    {items}
  </ol>
</aside>
"""


def render_toc(lang: str = DEFAULT_LANG) -> str:
    """Collapsible contents block shown on narrow screens (rail hidden)."""
    items = "\n    ".join(
        f'<a href="#{anchor}">{label}</a>' for anchor, label in _toc_entries(lang)
    )
    return f"""
<details class="toc-mobile">
  <summary>{tr(lang)["contents"]}</summary>
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


_KPI_LABEL_KEYS = [
    "kpi_gdp_growth",
    "kpi_unemployment",
    "kpi_inflation",
    "kpi_debt",
    "kpi_yield",
    "kpi_npl",
]


def render_kpi_dashboard(kpis: Dict, lang: str = DEFAULT_LANG) -> str:
    S = tr(lang)
    cards = []
    for (pillar_key, col, _en_label, fmt, suffix), label_key in zip(_KPI_DEFS, _KPI_LABEL_KEYS):
        label = S.get(label_key, _en_label)
        pillar_data = kpis.get(pillar_key, {})
        value = pillar_data.get(col)
        period = pillar_data.get("_date", "")
        if value is not None:
            formatted = f"{value:{fmt}}{suffix}"
            sem_cls = _KPI_SEMANTIC.get(col, lambda v: "neutral")(value)
            arrow, trend_cls = _kpi_trend(pillar_key, col)
            trend_html = (
                f'<span class="kpi-trend {trend_cls}">{arrow} {S["kpi_vs_prev"]}</span>'
                if arrow
                else ""
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
  <h2>{S["kpi_section_title"]}</h2>
  <div class="kpi-grid">
    {"".join(cards)}
  </div>
</section>
"""


_DEFAULT_SOURCE = "INE &middot; Banco de Portugal &middot; Eurostat &middot; ECB"


def _exhibit(
    inner_html: str,
    title: str,
    source: str = _DEFAULT_SOURCE,
    note: str = "",
    lang: str = DEFAULT_LANG,
) -> str:
    """Wrap a chart in the numbered-exhibit pattern: title above, source below."""
    note_html = f" &mdash; {note}" if note else ""
    return f"""
    <figure class="exhibit">
      <figcaption class="exhibit-head">{title}</figcaption>
      {inner_html}
      <p class="exhibit-source">{tr(lang)["source"]}: {source}{note_html}</p>
    </figure>"""


def render_stats_table(pillar_key: str, baseline: Dict, lang: str = DEFAULT_LANG) -> str:
    """Render a statistics table from DQ baseline data."""
    stats = baseline.get(pillar_key, {})
    if not stats:
        return ""
    S = tr(lang)
    rows = []
    for col, values in stats.items():
        label = _col_label(col, lang)
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
      <thead><tr><th>{S["th_indicator"]}</th><th>{S["th_mean"]}</th><th>{S["th_std"]}</th><th>{S["th_median"]}</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>"""


def render_pillar_section(
    insight: Dict,
    chart_filename: str,
    section_id: str,
    title: str,
    baseline: Dict,
    lang: str = DEFAULT_LANG,
) -> str:
    """Render a single pillar section."""
    S = tr(lang)
    headline = insight.get("headline", "")
    summary = insight.get("executive_summary", "")
    findings = insight.get("key_findings", [])
    risk = insight.get("risk_assessment", "")
    outlook = insight.get("outlook", "")
    # Prefer the language-neutral risk class token; fall back to parsing the prose
    # (which only works for English) for briefings produced before the token existed.
    risk_cls = insight.get("risk_class") or _risk_class(risk)

    primary_col = _PILLAR_PRIMARY_COL.get(section_id, "")
    plotly_div = _make_plotly_timeseries(section_id, title, primary_col, lang)
    col_label = _col_label(primary_col, lang)
    exhibit_title = f"{col_label}, {START_YEAR}&ndash;{END_YEAR}"
    chart_html = ""
    if plotly_div:
        chart_html = _exhibit(
            f'<div class="plotly-chart">{plotly_div}</div>',
            exhibit_title,
            note=S["interactive_note"],
            lang=lang,
        )
    else:
        chart_uri = encode_chart(chart_filename)
        if chart_uri:
            chart_html = _exhibit(
                f'<img src="{chart_uri}" alt="{_esc(title)}" loading="lazy">',
                exhibit_title,
                lang=lang,
            )

    findings_html = ""
    if findings:
        items = "\n".join(f"<li>{_esc(f)}</li>" for f in findings)
        findings_html = f"""
    <h3>{S["key_findings"]}</h3>
    <ul class="key-findings">{items}</ul>"""

    stats_html = render_stats_table(insight.get("pillar", section_id), baseline, lang)
    stats_section = ""
    if stats_html:
        stats_section = (
            f"<h3>{S['descriptive_statistics'].format(start=START_YEAR, end=END_YEAR)}</h3>"
            f"{stats_html}"
        )

    risk_html = ""
    if risk:
        risk_html = f"""
    <div class="risk-callout {risk_cls}">
      <strong>{S["risk_assessment"]}</strong> {_esc(risk)}
    </div>"""

    outlook_html = ""
    if outlook:
        outlook_html = f"<h3>{S['outlook']}</h3>{_paragraphs(outlook)}"

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


def render_cross_pillar(briefing: Dict, lang: str = DEFAULT_LANG) -> str:
    S = tr(lang)
    cross = briefing.get("cross_pillar_insights", {})
    narrative = cross.get("macro_narrative", "")
    relationships = cross.get("relationships", [])

    narrative_html = _paragraphs(narrative) if narrative else ""

    rel_cards = []
    for rel in relationships:
        name = rel.get("name", "")
        # The cross-pillar relationships store their prose under "narrative".
        desc = rel.get("narrative") or rel.get("description", "")
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
        ("correlation_heatmap.png", S["cap_correlation"]),
        ("phillips_curve.png", S["cap_phillips"]),
    ]:
        uri = encode_chart(fn)
        if uri:
            grid_charts.append(
                _exhibit(f'<img src="{uri}" alt="{caption}" loading="lazy">', caption, lang=lang)
            )

    # Crisis timeline full-width
    crisis_html = ""
    crisis_uri = encode_chart("crisis_timeline.png")
    if crisis_uri:
        crisis_html = _exhibit(
            f'<img src="{crisis_uri}" alt="{S["cap_crisis"]}" loading="lazy" style="width:100%;">',
            S["cap_crisis"],
            lang=lang,
        )

    return f"""
<section id="cross-pillar" class="analysis-section">
  <h2>{S["cross_pillar_title"]}</h2>
  {narrative_html}
  {rel_grid}
  <div class="chart-grid">
    {"".join(grid_charts)}
  </div>
  {crisis_html}
</section>
"""


def render_benchmarking(lang: str = DEFAULT_LANG) -> str:
    S = tr(lang)
    charts = []
    for fn, caption in [
        ("benchmark_radar_pt_vs_eu.png", S["cap_radar"]),
        ("benchmark_small_multiples.png", S["cap_small_multiples"]),
    ]:
        uri = encode_chart(fn)
        if uri:
            charts.append(
                _exhibit(f'<img src="{uri}" alt="{caption}" loading="lazy">', caption, lang=lang)
            )

    if not charts:
        return ""

    return f"""
<section id="benchmarking" class="analysis-section">
  <h2>{S["benchmarking_title"]}</h2>
  <p>{S["benchmarking_intro"]}</p>
  <div class="chart-grid">
    {"".join(charts)}
  </div>
</section>
"""


def render_regional_section(lang: str = DEFAULT_LANG) -> str:
    """Render the NUTS2 regional analysis section with interactive choropleth."""
    from config.settings import DATABASE_PATH
    from src.analysis.regional_analysis import build_choropleth_div, run_regional_analysis

    S = tr(lang)
    db_path = str(DATABASE_PATH)
    regional = run_regional_analysis(db_path, lang=lang)
    choropleth_div = (
        build_choropleth_div(db_path, include_plotlyjs=_plotly_include_arg(), lang=lang)
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
        <th>{S["regional_th_code"]}</th><th>{S["regional_th_region"]}</th>
        <th style="text-align:right;">{S["regional_th_gdp"]}</th>
        <th style="text-align:right;">{S["regional_th_unemp"]}</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>"""

    map_html = ""
    if choropleth_div:
        map_html = _exhibit(
            f'<div class="plotly-chart">{choropleth_div}</div>',
            S["regional_map_title"],
            source=S["regional_source"],
            note=S["regional_map_note"],
            lang=lang,
        )

    source_note = ""
    if regional.get("source") == "synthetic_fallback":
        source_note = (
            '<p style="font-size:0.82rem;color:var(--medium-gray);margin-top:1rem;">'
            f"<em>{S['regional_synthetic_note']}</em></p>"
        )

    return f"""
<section id="regional" class="analysis-section">
  <h2>{S["regional_title"]}</h2>
  <p>{S["regional_intro"]}</p>
  {map_html}
  {table_html}
  {findings_html}
  {source_note}
</section>
"""


def render_executive_dashboard(lang: str = DEFAULT_LANG) -> str:
    """Render the executive dashboard overview chart."""
    S = tr(lang)
    uri = encode_chart("economic_dashboard.png")
    if not uri:
        return ""
    dashboard_exhibit = _exhibit(
        f'<img src="{uri}" alt="{S["exec_dashboard_title"]}" loading="lazy">',
        S["exec_dashboard_caption"].format(start=START_YEAR, end=END_YEAR),
        lang=lang,
    )
    return f"""
<section id="executive-dashboard" class="analysis-section">
  <h2>{S["exec_dashboard_title"]}</h2>
  <p>{S["exec_dashboard_intro"].format(start=START_YEAR, end=END_YEAR)}</p>
  {dashboard_exhibit}
</section>
"""


def render_stl_decomposition(lang: str = DEFAULT_LANG) -> str:
    """Render STL seasonal-trend decomposition charts."""
    S = tr(lang)
    stl_charts = [
        ("stl_real_gdp.png", S["cap_stl_gdp"]),
        ("stl_unemployment_rate.png", S["cap_stl_unemployment"]),
        ("stl_hicp_inflation.png", S["cap_stl_inflation"]),
    ]
    charts = []
    for fn, caption in stl_charts:
        uri = encode_chart(fn)
        if uri:
            charts.append(
                _exhibit(f'<img src="{uri}" alt="{caption}" loading="lazy">', caption, lang=lang)
            )

    if not charts:
        return ""

    return f"""
<section id="stl-decomposition" class="analysis-section">
  <h2>{S["stl_title"]}</h2>
  <p>{S["stl_intro"]}</p>
  <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:1.5rem;">
    {"".join(charts)}
  </div>
</section>
"""


def render_forecasting(lang: str = DEFAULT_LANG) -> str:
    """Render SARIMAX 12-quarter-ahead forecasts with Plotly interactive charts."""
    S = tr(lang)
    fc_labels = FORECAST_INDICATORS.get(lang, FORECAST_INDICATORS[DEFAULT_LANG])
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

        indicator = fc_labels.get(
            pillar, fc_data.get("indicator", pillar.replace("_", " ").title())
        )
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
                            name=S["fc_historical"],
                            line={"color": "#1A1A2E", "width": 2},
                            hovertemplate=(
                                "<b>%{x}</b><br>" + S["fc_historical"] + ": %{y:.2f}<extra></extra>"
                            ),
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
                name=S["fc_forecast_name"].format(method=method),
                line={"color": "#2251FF", "width": 2.25, "dash": "dot"},
                hovertemplate=(
                    "<b>%{x}</b><br>" + S["fc_th_forecast"] + ": %{y:.2f}<extra></extra>"
                ),
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
                    S["fc_chart_title"].format(indicator=_esc(indicator)),
                    source=S["fc_source"],
                    note=S["fc_note"].format(method=method),
                    lang=lang,
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
        indicator = fc_labels.get(pillar, fc_data.get("indicator", pillar.title()))
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
            f"<th>{S['fc_th_indicator']}</th><th>{S['fc_th_latest_period']}</th>"
            f"<th>{S['fc_th_latest_value']}</th>"
            f"<th>{S['fc_th_horizon']}</th><th>{S['fc_th_forecast']}</th>"
            f"<th>{S['fc_th_direction']}</th>"
            "</tr></thead>"
            f'<tbody>{"".join(table_rows)}</tbody>'
            "</table></div>"
        )

    return f"""
<section id="forecasting" class="analysis-section">
  <h2>{S["forecasting_title"]}</h2>
  <p>{S["forecasting_intro"]}</p>
  {table_html}
  {"".join(charts_html)}
</section>
"""


def render_risk_matrix(briefing: Dict, lang: str = DEFAULT_LANG) -> str:
    S = tr(lang)
    risks = briefing.get("risk_matrix", [])
    if not risks:
        return ""

    pillar_titles = PILLAR_TITLES.get(lang, PILLAR_TITLES[DEFAULT_LANG])
    rows = []
    for r in risks:
        pillar_key = r.get("pillar", "")
        pillar = pillar_titles.get(pillar_key, pillar_key.replace("_", " ").title())
        level = r.get("risk_level", "moderate")
        desc = r.get("description", "")
        cls = r.get("risk_class") or _risk_class(level)
        rows.append(
            f"<tr><td><strong>{_esc(pillar)}</strong></td>"
            f'<td><span class="risk-badge {cls}">{_esc(level)}</span></td>'
            f"<td>{_esc(desc)}</td></tr>"
        )

    return f"""
<section id="risk-matrix" class="analysis-section">
  <h2>{S["risk_matrix_title"]}</h2>
  <table class="risk-matrix">
    <thead><tr><th>{S["rm_th_pillar"]}</th><th>{S["rm_th_level"]}</th><th>{S["rm_th_assessment"]}</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>
"""


def render_recommendations(briefing: Dict, lang: str = DEFAULT_LANG) -> str:
    recs = briefing.get("strategic_recommendations", [])
    if not recs:
        return ""
    items = "\n".join(f"<li>{_esc(r)}</li>" for r in recs)
    return f"""
<section id="recommendations" class="analysis-section">
  <h2>{tr(lang)["recommendations_title"]}</h2>
  <ol class="recommendations-list">{items}</ol>
</section>
"""


def render_platform(lang: str = DEFAULT_LANG) -> str:
    """Render the Platform & Tools section showcasing v2 capabilities."""
    S = tr(lang)
    return f"""
<section id="platform" class="analysis-section">
  <h2>{S["platform_title"]}</h2>
  <p>{S["platform_intro"].format(version=VERSION)}</p>
  <div class="chart-grid">
    <div class="info-card">
      <strong>{S["platform_dashboard_h"]}</strong>
      <p>{S["platform_dashboard_p"]}</p>
      <p class="launch">{S["launch"]} <code>streamlit run dashboard/app.py</code></p>
    </div>
    <div class="info-card">
      <strong>{S["platform_api_h"]}</strong>
      <p>{S["platform_api_p"]}</p>
      <p class="launch">{S["launch"]} <code>uvicorn api.main:app --reload</code></p>
    </div>
    <div class="info-card">
      <strong>{S["platform_forecast_h"]}</strong>
      <p>{S["platform_forecast_p"]}</p>
    </div>
    <div class="info-card">
      <strong>{S["platform_powerbi_h"]}</strong>
      <p>{S["platform_powerbi_p"]}</p>
    </div>
  </div>
  <p style="margin-top:1.2rem; font-size:0.9rem;">
    {S["platform_footnote"]}
  </p>
</section>
"""


def render_methodology(lang: str = DEFAULT_LANG) -> str:
    S = tr(lang)
    source_rows = []
    for name, url in DATA_SOURCES.items():
        source_rows.append(f"<tr><td>{_esc(name)}</td><td>{_esc(url)}</td></tr>")

    return f"""
<section id="methodology" class="methodology-section">
  <h2>{S["methodology_title"]}</h2>
  <p>{S["methodology_intro"].format(start=START_YEAR, end=END_YEAR)}</p>
  <table class="source-table">
    <thead><tr><th>{S["methodology_th_source"]}</th><th>{S["methodology_th_url"]}</th></tr></thead>
    <tbody>{"".join(source_rows)}</tbody>
  </table>
  <p style="margin-top:1rem; font-size:0.85rem; color:var(--medium-gray);">
    {S["methodology_granularity"]}<br>
    {S["methodology_quality"]}<br>
    {S["methodology_engine"]}<br>
    {S["methodology_delivery"]}<br>
    {S["methodology_version"].format(version=VERSION, date=datetime.now().strftime("%d %B %Y"))}
  </p>
</section>
"""


def render_footer(lang: str = DEFAULT_LANG) -> str:
    S = tr(lang)
    generated = datetime.now().strftime("%d %B %Y, %H:%M")
    return f"""
<footer>
  <div class="author">{S["footer_author_line"].format(version=VERSION)}</div>
  <p>{S["footer_tagline"]}</p>
  <p style="font-size:0.75rem; color:var(--medium-gray); margin-top:0.25rem;">{S["footer_generated"].format(generated=generated)}</p>
</footer>
"""


# =============================================================================
# MAIN GENERATOR
# =============================================================================


def render_lang_switch(current: str) -> str:
    """Build the fixed-position EN/PT language toggle."""
    links = []
    for code in SUPPORTED_LANGS:
        href = _OUTPUT_NAME.get(code, "index.html")
        cls = ' class="active"' if code == current else ""
        # The non-current link is tagged so the preference script can redirect to it.
        oid = "" if code == current else ' id="lang-other"'
        links.append(
            f'<a href="{href}" data-lang="{code}" hreflang="{code}"'
            f'{cls}{oid} title="{LANG_FULL[code]}">{LANG_NAMES[code]}</a>'
        )
    label = tr(current)["lang_switch_label"]
    return f'<nav id="lang-switch" aria-label="{label}">{"".join(links)}</nav>'


def generate_report(output_path: Optional[Path] = None, lang: str = DEFAULT_LANG) -> Path:
    """Generate the full HTML report for ``lang`` and write to disk.

    English writes to ``docs/index.html`` (the canonical entry point); Portuguese
    writes to ``docs/index.pt.html``. A language toggle in each file links to the
    other and remembers the choice in ``localStorage``.
    """
    ensure_directories()
    lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG

    # Reset so plotly.js is embedded exactly once per report (matters when
    # generate_report() is called more than once in the same process).
    _PLOTLY_STATE["included"] = False

    if output_path is None:
        output_path = _output_for_lang(lang)

    S = tr(lang)
    logger.info("Generating HTML report (lang=%s)...", lang)

    # Load data
    briefing = load_latest_briefing(lang)
    kpis = load_kpi_values()
    baseline = load_dq_baseline()

    # Build pillar insights lookup
    pillar_insights = {}
    for pi in briefing.get("pillar_insights", []):
        pillar_insights[pi.get("pillar", "")] = pi

    pillar_titles = PILLAR_TITLES.get(lang, PILLAR_TITLES[DEFAULT_LANG])

    # Render sections: editorial cover, then a two-column shell with a sticky
    # contents rail (desktop) and the content column.
    sections = [
        render_hero(briefing, kpis, lang),
        '<div class="layout">',
        render_side_rail(lang),
        '<div class="content">',
        render_toc(lang),
        "<main>",
        render_kpi_dashboard(kpis, lang),
    ]

    # Pillar sections
    for key, title, chart_fn, _ in _PILLAR_CONFIG:
        insight = pillar_insights.get(key, {})
        loc_title = pillar_titles.get(key, title)
        sections.append(render_pillar_section(insight, chart_fn, key, loc_title, baseline, lang))

    # Executive dashboard, cross-pillar, STL, benchmarking, regional, risk, recommendations, platform
    sections.extend(
        [
            render_executive_dashboard(lang),
            render_cross_pillar(briefing, lang),
            render_stl_decomposition(lang),
            render_forecasting(lang),
            render_benchmarking(lang),
            render_regional_section(lang),
            render_risk_matrix(briefing, lang),
            render_recommendations(briefing, lang),
            render_platform(lang),
            render_methodology(lang),
            "</main>",
            "</div>",
            "</div>",
            render_footer(lang),
        ]
    )

    body = "\n".join(sections)

    js_block = """<script>
// Language preference: honour the visitor's last choice, then remember new ones.
(function () {
  var KEY = "pdi_lang";
  var cur = document.documentElement.lang || "en";
  var other = document.getElementById("lang-other");
  try {
    var pref = localStorage.getItem(KEY);
    if (pref && pref !== cur && other) {
      location.replace(other.getAttribute("href"));
      return;
    }
  } catch (e) {}
  var langLinks = document.querySelectorAll("#lang-switch a");
  for (var i = 0; i < langLinks.length; i++) {
    langLinks[i].addEventListener("click", function () {
      try { localStorage.setItem(KEY, this.getAttribute("data-lang")); } catch (e) {}
    });
  }
})();
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
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{S["html_title"]}</title>
  <style>{CSS}</style>
</head>
<body>
<div id="progress-bar"></div>
{render_lang_switch(lang)}
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


def generate_all_reports(langs=SUPPORTED_LANGS) -> "list[Path]":
    """Generate the report for every supported language (default: en + pt)."""
    return [generate_report(lang=code) for code in langs]


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
        help="Output path (default: docs/index.html for en, docs/index.pt.html for pt)",
    )
    parser.add_argument(
        "--lang",
        choices=list(SUPPORTED_LANGS),
        default=DEFAULT_LANG,
        help="Report language (default: en). Ignored when --all is used.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Generate every supported language (en + pt) to docs/.",
    )
    args = parser.parse_args()
    if args.all:
        for p in generate_all_reports():
            print(f"Report ready: {p}")
    else:
        path = generate_report(output_path=args.output, lang=args.lang)
        print(f"Report ready: {path}")
