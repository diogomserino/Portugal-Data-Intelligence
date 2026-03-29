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
}

# Pillar display config: (pillar_key, title, chart_filename, icon)
_PILLAR_CONFIG = [
    ("gdp", "Gross Domestic Product", "gdp_evolution.png", ""),
    ("unemployment", "Labour Market & Employment", "unemployment_trends.png", ""),
    ("credit", "Credit to the Economy", "credit_portfolio.png", ""),
    ("interest_rates", "Interest Rate Environment", "interest_rate_environment.png", ""),
    ("inflation", "Price Stability & Inflation", "inflation_dashboard.png", ""),
    ("public_debt", "Public Debt Sustainability", "public_debt_sustainability.png", ""),
]

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


# =============================================================================
# CSS DESIGN SYSTEM
# =============================================================================

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  --navy: #1A1A2E;
  --dark-slate: #3D3D5C;
  --deep-red: #9B2226;
  --forest-green: #386641;
  --warm-gold: #D4A373;
  --steel-blue: #4A6FA5;
  --off-white: #FFFFFF;
  --light-gray: #F5F5F5;
  --border: #D0D0D0;
  --medium-gray: #888;
  --risk-low: #386641;
  --risk-moderate: #D4A373;
  --risk-elevated: #E65100;
  --risk-high: #9B2226;
  --font-heading: 'Playfair Display', Georgia, 'Times New Roman', serif;
  --font-body: 'Inter', 'Segoe UI', -apple-system, sans-serif;
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
  background: linear-gradient(135deg, var(--navy) 0%, #2D2D4E 100%);
  color: #fff;
  padding: 4rem 2rem 3rem;
  text-align: center;
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
  transition: box-shadow 0.2s;
}
.kpi-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.kpi-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--navy);
  line-height: 1.2;
}
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
  color: var(--border);
  margin-top: 0.2rem;
}

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

/* --- RESPONSIVE --- */
@media (max-width: 768px) {
  .hero h1 { font-size: 1.8rem; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .chart-grid { grid-template-columns: 1fr !important; }
  main { padding: 0 1rem; }
}

/* --- PRINT --- */
@media print {
  .hero { background: var(--navy) !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .toc { display: none; }
  .pillar-section, .analysis-section { page-break-before: auto; page-break-inside: avoid; }
  body { font-size: 11pt; }
  .kpi-card { border: 1px solid #ccc; }
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


def render_hero(briefing: Dict) -> str:
    title = briefing.get("title", "Portugal Macroeconomic Intelligence Briefing")
    date = briefing.get("date", datetime.now().strftime("%d %B %Y"))
    summary = briefing.get("overall_assessment", "")
    return f"""
<header class="hero">
  <h1>{_esc(title)}</h1>
  <div class="subtitle">Macroeconomic Analysis of the Portuguese Economy {START_YEAR}&ndash;{END_YEAR}</div>
  <div class="meta">{_esc(date)} &middot; Portugal Data Intelligence</div>
  <div class="executive-summary">
    {_paragraphs(summary)}
  </div>
</header>
"""


def render_toc() -> str:
    links = []
    for key, title, _, icon in _PILLAR_CONFIG:
        links.append(f'<a href="#{key}">{title}</a>')
    links.extend([
        '<a href="#cross-pillar">Cross-Pillar Analysis</a>',
        '<a href="#benchmarking">EU Benchmarking</a>',
        '<a href="#risk-matrix">Risk Matrix</a>',
        '<a href="#recommendations">Strategic Recommendations</a>',
        '<a href="#platform">Platform & Tools</a>',
        '<a href="#methodology">Methodology</a>',
    ])
    items = "\n    ".join(links)
    return f"""
<nav class="toc">
  <h2>Contents</h2>
  <div class="toc-grid">
    {items}
  </div>
</nav>
"""


def render_kpi_dashboard(kpis: Dict) -> str:
    cards = []
    for pillar_key, col, label, fmt, suffix in _KPI_DEFS:
        pillar_data = kpis.get(pillar_key, {})
        value = pillar_data.get(col)
        period = pillar_data.get("_date", "")
        if value is not None:
            formatted = f"{value:{fmt}}{suffix}"
        else:
            formatted = "N/A"
        cards.append(f"""
      <div class="kpi-card">
        <div class="kpi-value">{formatted}</div>
        <div class="kpi-label">{_esc(label)}</div>
        <div class="kpi-period">{_esc(period)}</div>
      </div>""")

    return f"""
<section id="key-indicators" class="kpi-dashboard">
  <h2>Key Indicators — Latest Values</h2>
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

    chart_uri = encode_chart(chart_filename)
    chart_html = ""
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
        stats_section = f"<h3>Descriptive Statistics ({START_YEAR}&ndash;{END_YEAR})</h3>{stats_html}"

    risk_html = ""
    if risk:
        risk_html = f"""
    <div class="risk-callout {risk_cls}">
      <strong>Risk Assessment:</strong> {_esc(risk)}
    </div>"""

    outlook_html = ""
    if outlook:
        outlook_html = f"<h3>Outlook</h3>{_paragraphs(outlook)}"

    return f"""
<section id="{section_id}" class="pillar-section">
  <h2>{_esc(title)}</h2>
  <p style="font-size:1.05rem; font-weight:500; color:var(--navy); margin-bottom:1rem;">{_esc(headline)}</p>
  <div class="pillar-narrative">{_paragraphs(summary)}</div>
  {chart_html}
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
  <p>Portugal Data Intelligence v2.1 delivers insights through multiple complementary channels,
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
  <p>This report analyses the Portuguese economy across six macroeconomic pillars
  using data from {START_YEAR} to {END_YEAR}. All data is sourced from authoritative
  national and European statistical institutions.</p>
  <table class="source-table">
    <thead><tr><th>Source</th><th>URL</th></tr></thead>
    <tbody>{"".join(source_rows)}</tbody>
  </table>
  <p style="margin-top:1rem; font-size:0.85rem; color:var(--medium-gray);">
    <strong>Granularity:</strong> GDP and Public Debt are quarterly; Unemployment,
    Credit, Interest Rates, and Inflation are monthly.<br>
    <strong>Data Quality:</strong> All data passes a 7-layer validation framework
    (schema, nulls, ranges, outliers, drift, consistency, freshness).<br>
    <strong>Analysis Engine:</strong> Python (pandas, statsmodels, scipy) with
    SQLite storage, ensemble forecasting, and automated reporting.<br>
    <strong>Delivery:</strong> Power BI, Streamlit dashboard, self-contained HTML, REST API (FastAPI).<br>
    <strong>Version:</strong> 2.1.0 &mdash; March 2026
  </p>
</section>
"""


def render_footer() -> str:
    return """
<footer>
  <div class="author">Portugal Data Intelligence v2.1</div>
  <p>dms1996 &middot; Portfolio 2026 &middot; Power BI &middot; Streamlit &middot; FastAPI &middot; HTML</p>
</footer>
"""


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_report(output_path: Optional[Path] = None) -> Path:
    """Generate the full HTML report and write to disk."""
    ensure_directories()

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
        render_hero(briefing),
        render_toc(),
        "<main>",
        render_kpi_dashboard(kpis),
    ]

    # Pillar sections
    for key, title, chart_fn, _ in _PILLAR_CONFIG:
        insight = pillar_insights.get(key, {})
        sections.append(
            render_pillar_section(insight, chart_fn, key, title, baseline)
        )

    # Executive dashboard, cross-pillar, STL, benchmarking, risk, recommendations, platform
    sections.extend([
        render_executive_dashboard(),
        render_cross_pillar(briefing),
        render_stl_decomposition(),
        render_benchmarking(),
        render_risk_matrix(briefing),
        render_recommendations(briefing),
        render_platform(),
        render_methodology(),
        "</main>",
        render_footer(),
    ])

    body = "\n".join(sections)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Portugal Macroeconomic Intelligence Briefing</title>
  <style>{CSS}</style>
</head>
<body>
{body}
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
        "--output", "-o",
        type=Path,
        default=None,
        help="Output path (default: dashboard/pages/portugal_economic_report.html)",
    )
    args = parser.parse_args()
    path = generate_report(output_path=args.output)
    print(f"Report ready: {path}")
