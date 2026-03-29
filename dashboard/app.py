"""
Portugal Data Intelligence - Interactive Dashboard
====================================================
Streamlit-based interactive dashboard for exploring Portuguese
macroeconomic data across all six economic pillars.

Usage:
    streamlit run dashboard/app.py
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Project setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH

# ---------------------------------------------------------------------------
# Streamlit config (must be first st call)
# ---------------------------------------------------------------------------
import streamlit as st

st.set_page_config(
    page_title="Portugal Data Intelligence",
    page_icon="🇵🇹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Colour palette (consistent with shared_styles)
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#9B2226",
    "secondary": "#386641",
    "accent": "#D4A373",
    "positive": "#386641",
    "negative": "#9B2226",
    "neutral": "#3D3D5C",
    "background": "#FFFFFF",
    "light_text": "#6B7280",
}

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

_VALID_TABLES = frozenset({
    "fact_gdp", "fact_unemployment", "fact_credit",
    "fact_interest_rates", "fact_inflation", "fact_public_debt",
})
_VALID_DATE_COLS = frozenset({"date_key"})


@st.cache_data(ttl=300)
def load_data(table: str, date_col: str = "date_key") -> pd.DataFrame:
    """Load a fact table from the SQLite database."""
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table: {table}")
    if date_col not in _VALID_DATE_COLS:
        raise ValueError(f"Invalid date column: {date_col}")
    db_path = str(DATABASE_PATH)
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql(f"SELECT d.*, f.* FROM {table} f JOIN dim_date d ON f.date_key = d.date_key ORDER BY d.year, d.month", conn)
    except sqlite3.OperationalError:
        df = pd.read_sql(f"SELECT * FROM {table} ORDER BY {date_col}", conn)
    finally:
        conn.close()
    return df


@st.cache_data(ttl=300)
def load_all_pillars() -> dict:
    """Load all six pillar datasets."""
    return {
        "GDP": load_data("fact_gdp"),
        "Unemployment": load_data("fact_unemployment"),
        "Credit": load_data("fact_credit"),
        "Interest Rates": load_data("fact_interest_rates"),
        "Inflation": load_data("fact_inflation"),
        "Public Debt": load_data("fact_public_debt"),
    }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def parse_date_key(df: pd.DataFrame) -> pd.DataFrame:
    """Add a proper datetime column from date_key."""
    df = df.copy()
    sample = str(df["date_key"].iloc[0])
    if "Q" in sample:
        # Quarterly: "2010-Q1" -> datetime
        def to_date(v):
            parts = str(v).split("-Q")
            year, q = int(parts[0]), int(parts[1])
            month = (q - 1) * 3 + 1
            return pd.Timestamp(year=year, month=month, day=1)
        df["date"] = df["date_key"].apply(to_date)
    else:
        # Monthly: "2010-01" -> datetime
        df["date"] = pd.to_datetime(df["date_key"], format="%Y-%m")
    return df


def metric_card(label: str, value: str, delta: str = None, delta_color: str = "normal"):
    """Display a metric in streamlit."""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def fmt(val, decimals=1, suffix=""):
    """Format a number for display."""
    if val is None or pd.isna(val):
        return "N/A"
    return f"{val:,.{decimals}f}{suffix}"


# ---------------------------------------------------------------------------
# Page: Executive Overview
# ---------------------------------------------------------------------------

def page_overview():
    st.title("Portugal Economic Dashboard")
    st.markdown("**Macroeconomic Intelligence Platform** — Data from 2010 to 2025")

    data = load_all_pillars()

    # KPI row
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    # GDP
    gdp = data["GDP"]
    if not gdp.empty:
        latest_gdp = gdp["nominal_gdp"].iloc[-1]
        prev_gdp = gdp["nominal_gdp"].iloc[-5] if len(gdp) > 5 else gdp["nominal_gdp"].iloc[0]
        gdp_change = ((latest_gdp - prev_gdp) / prev_gdp * 100)
        col1.metric("GDP (EUR M)", fmt(latest_gdp, 0), f"{gdp_change:+.1f}%")

    # Unemployment
    unemp = data["Unemployment"]
    if not unemp.empty:
        latest_u = unemp["unemployment_rate"].iloc[-1]
        prev_u = unemp["unemployment_rate"].iloc[-13] if len(unemp) > 13 else unemp["unemployment_rate"].iloc[0]
        col2.metric("Unemployment", fmt(latest_u, 1, "%"), f"{latest_u - prev_u:+.1f}pp", delta_color="inverse")

    # Credit
    credit = data["Credit"]
    if not credit.empty:
        latest_c = credit["total_credit"].iloc[-1]
        col3.metric("Total Credit (EUR M)", fmt(latest_c, 0))

    # Interest Rates
    rates = data["Interest Rates"]
    if not rates.empty:
        latest_r = rates["portugal_10y_bond_yield"].iloc[-1]
        col4.metric("10Y Bond Yield", fmt(latest_r, 2, "%"))

    # Inflation
    infl = data["Inflation"]
    if not infl.empty:
        latest_i = infl["hicp"].iloc[-1]
        col5.metric("HICP Inflation", fmt(latest_i, 1, "%"))

    # Public Debt
    debt = data["Public Debt"]
    if not debt.empty:
        latest_d = debt["debt_to_gdp_ratio"].iloc[-1]
        col6.metric("Debt/GDP", fmt(latest_d, 1, "%"))

    st.divider()

    # Dashboard charts (2x3 grid)
    panels = [
        ("GDP Evolution", data["GDP"], "nominal_gdp", "EUR M"),
        ("Unemployment Rate", data["Unemployment"], "unemployment_rate", "%"),
        ("Total Credit", data["Credit"], "total_credit", "EUR M"),
        ("10Y Bond Yield", data["Interest Rates"], "portugal_10y_bond_yield", "%"),
        ("HICP Inflation", data["Inflation"], "hicp", "%"),
        ("Debt-to-GDP Ratio", data["Public Debt"], "debt_to_gdp_ratio", "%"),
    ]

    row1 = st.columns(3)
    row2 = st.columns(3)
    all_cols = row1 + row2

    for idx, (title, df, col, unit) in enumerate(panels):
        if df.empty:
            continue
        df = parse_date_key(df)
        with all_cols[idx]:
            fig = px.line(
                df, x="date", y=col,
                title=title,
                labels={col: unit, "date": ""},
                color_discrete_sequence=[COLORS["primary"]],
            )
            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=False,
                hovermode="x unified",
            )
            fig.update_traces(line=dict(width=2))
            st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Pillar Deep Dive
# ---------------------------------------------------------------------------

def page_pillar_detail():
    st.title("Pillar Deep Dive")

    pillar_config = {
        "GDP": {
            "table": "fact_gdp",
            "columns": ["nominal_gdp", "real_gdp", "gdp_growth_yoy", "gdp_per_capita"],
            "labels": {
                "nominal_gdp": "Nominal GDP (EUR M)",
                "real_gdp": "Real GDP (EUR M)",
                "gdp_growth_yoy": "YoY Growth (%)",
                "gdp_per_capita": "GDP per Capita (EUR)",
            },
        },
        "Unemployment": {
            "table": "fact_unemployment",
            "columns": ["unemployment_rate", "youth_unemployment_rate", "long_term_unemployment_rate", "labour_force_participation_rate"],
            "labels": {
                "unemployment_rate": "Total (%)",
                "youth_unemployment_rate": "Youth (%)",
                "long_term_unemployment_rate": "Long-term (%)",
                "labour_force_participation_rate": "Participation Rate (%)",
            },
        },
        "Credit": {
            "table": "fact_credit",
            "columns": ["total_credit", "credit_nfc", "credit_households", "npl_ratio"],
            "labels": {
                "total_credit": "Total Credit (EUR M)",
                "credit_nfc": "NFC Credit (EUR M)",
                "credit_households": "Household Credit (EUR M)",
                "npl_ratio": "NPL Ratio (%)",
            },
        },
        "Interest Rates": {
            "table": "fact_interest_rates",
            "columns": ["ecb_main_refinancing_rate", "euribor_3m", "euribor_12m", "portugal_10y_bond_yield"],
            "labels": {
                "ecb_main_refinancing_rate": "ECB Main Rate (%)",
                "euribor_3m": "Euribor 3M (%)",
                "euribor_12m": "Euribor 12M (%)",
                "portugal_10y_bond_yield": "PT 10Y Yield (%)",
            },
        },
        "Inflation": {
            "table": "fact_inflation",
            "columns": ["hicp", "cpi_estimated", "core_inflation"],
            "labels": {
                "hicp": "HICP (%)",
                "cpi_estimated": "CPI Estimated (%)",
                "core_inflation": "Core Inflation (%)",
            },
        },
        "Public Debt": {
            "table": "fact_public_debt",
            "columns": ["debt_to_gdp_ratio", "budget_deficit", "budget_deficit_annual",
                         "external_debt_share_estimated"],
            "labels": {
                "debt_to_gdp_ratio": "Debt/GDP (%)",
                "budget_deficit": "Budget Deficit Quarterly (% GDP)",
                "budget_deficit_annual": "Budget Deficit Annual (% GDP)",
                "external_debt_share_estimated": "External Debt Share Est. (%)",
            },
        },
    }

    selected_pillar = st.sidebar.selectbox("Select Pillar", list(pillar_config.keys()))
    config = pillar_config[selected_pillar]

    df = load_data(config["table"])
    if df.empty:
        st.warning(f"No data available for {selected_pillar}.")
        return

    df = parse_date_key(df)

    # Year range filter
    years = sorted(df["year"].unique())
    year_range = st.sidebar.slider(
        "Year Range",
        min_value=int(min(years)),
        max_value=int(max(years)),
        value=(int(min(years)), int(max(years))),
    )
    df = df[(df["year"] >= year_range[0]) & (df["year"] <= year_range[1])]

    # Column selector
    available_cols = [c for c in config["columns"] if c in df.columns]
    selected_cols = st.sidebar.multiselect(
        "Indicators",
        available_cols,
        default=available_cols[:2],
        format_func=lambda c: config["labels"].get(c, c),
    )

    if not selected_cols:
        st.info("Select at least one indicator from the sidebar.")
        return

    # Main chart
    fig = go.Figure()
    colors = [COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["neutral"]]
    for i, col in enumerate(selected_cols):
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df[col],
            name=config["labels"].get(col, col),
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate="%{x|%Y-%m}<br>%{y:.2f}<extra></extra>",
        ))

    fig.update_layout(
        title=f"{selected_pillar} — Detailed View ({year_range[0]}-{year_range[1]})",
        height=500,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Statistics table
    st.subheader("Descriptive Statistics")
    stats_data = {}
    for col in selected_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        stats_data[config["labels"].get(col, col)] = {
            "Latest": f"{series.iloc[-1]:.2f}",
            "Mean": f"{series.mean():.2f}",
            "Median": f"{series.median():.2f}",
            "Std Dev": f"{series.std():.2f}",
            "Min": f"{series.min():.2f}",
            "Max": f"{series.max():.2f}",
        }
    if stats_data:
        st.dataframe(pd.DataFrame(stats_data).T, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Correlation Matrix
# ---------------------------------------------------------------------------

def page_correlation():
    st.title("Cross-Pillar Correlation Analysis")

    data = load_all_pillars()

    # Build a merged annual dataset
    annual_data = {}

    gdp = data["GDP"]
    if not gdp.empty:
        annual_data["GDP Growth"] = gdp.groupby(parse_date_key(gdp)["date"].dt.year)["gdp_growth_yoy"].mean()

    unemp = data["Unemployment"]
    if not unemp.empty:
        annual_data["Unemployment"] = unemp.groupby(parse_date_key(unemp)["date"].dt.year)["unemployment_rate"].mean()

    infl = data["Inflation"]
    if not infl.empty:
        annual_data["Inflation (HICP)"] = infl.groupby(parse_date_key(infl)["date"].dt.year)["hicp"].mean()

    rates = data["Interest Rates"]
    if not rates.empty:
        annual_data["10Y Bond Yield"] = rates.groupby(parse_date_key(rates)["date"].dt.year)["portugal_10y_bond_yield"].mean()

    debt = data["Public Debt"]
    if not debt.empty:
        annual_data["Debt/GDP"] = debt.groupby(parse_date_key(debt)["date"].dt.year)["debt_to_gdp_ratio"].mean()

    if len(annual_data) < 2:
        st.warning("Insufficient data for correlation analysis.")
        return

    merged = pd.DataFrame(annual_data).dropna()

    corr = merged.corr()

    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale=["#9B2226", "#FFFFFF", "#386641"],
        zmin=-1, zmax=1,
        title="Pearson Correlation Matrix (Annual Averages)",
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    # Phillips Curve
    st.subheader("Phillips Curve (Unemployment vs Inflation)")
    if "Unemployment" in annual_data and "Inflation (HICP)" in annual_data:
        scatter_df = merged[["Unemployment", "Inflation (HICP)"]].copy()
        scatter_df["Year"] = scatter_df.index
        fig2 = px.scatter(
            scatter_df, x="Unemployment", y="Inflation (HICP)",
            text="Year",
            color_discrete_sequence=[COLORS["primary"]],
            trendline="ols",
            title="Phillips Curve: Unemployment vs Inflation",
        )
        fig2.update_traces(textposition="top center", marker=dict(size=10))
        fig2.update_layout(height=450)
        st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Data Explorer
# ---------------------------------------------------------------------------

def page_data_explorer():
    st.title("Raw Data Explorer")

    tables = {
        "GDP": "fact_gdp",
        "Unemployment": "fact_unemployment",
        "Credit": "fact_credit",
        "Interest Rates": "fact_interest_rates",
        "Inflation": "fact_inflation",
        "Public Debt": "fact_public_debt",
    }

    selected = st.selectbox("Select Table", list(tables.keys()))
    df = load_data(tables[selected])

    st.dataframe(df, use_container_width=True, height=500)

    # Download button
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv,
        file_name=f"{tables[selected]}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Main app with navigation
# ---------------------------------------------------------------------------

def main():
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Executive Overview", "Pillar Deep Dive", "Correlation Analysis", "Data Explorer"],
    )

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Portugal Data Intelligence**\n\n"
        "Macroeconomic analytics platform\n\n"
        "Data: 2010-2025 | 6 Pillars\n\n"
        "Sources: INE, Eurostat, ECB, BdP"
    )

    # Check database exists
    if not DATABASE_PATH.exists():
        st.error(
            f"Database not found at `{DATABASE_PATH}`.\n\n"
            "Run `python main.py --mode etl` to generate the database first."
        )
        return

    if page == "Executive Overview":
        page_overview()
    elif page == "Pillar Deep Dive":
        page_pillar_detail()
    elif page == "Correlation Analysis":
        page_correlation()
    elif page == "Data Explorer":
        page_data_explorer()


if __name__ == "__main__":
    main()
