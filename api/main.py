"""
Portugal Data Intelligence — REST API
=======================================
FastAPI-based REST API exposing macroeconomic data and insights.

Usage:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET /                           → API info
    GET /api/v1/pillars             → List all pillars
    GET /api/v1/pillars/{pillar}    → Latest data for a pillar
    GET /api/v1/pillars/{pillar}/timeseries → Full timeseries with filters
    GET /api/v1/alerts              → Active alerts
    GET /api/v1/correlation         → Cross-pillar correlation matrix
    GET /api/v1/health              → Health check
"""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Project setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH, DATA_PILLARS, API_ALLOWED_ORIGINS, API_KEY

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Portugal Data Intelligence API",
    description="Macroeconomic data and analytics for Portugal (2010-2025)",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=API_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def check_api_key(request: Request, call_next):
    """Require X-API-Key header when API_KEY is configured."""
    if API_KEY and request.url.path not in ("/", "/docs", "/redoc", "/openapi.json"):
        provided = request.headers.get("X-API-Key", "")
        if provided != API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)

# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------

PILLAR_TABLES = {
    "gdp": "fact_gdp",
    "unemployment": "fact_unemployment",
    "credit": "fact_credit",
    "interest_rates": "fact_interest_rates",
    "inflation": "fact_inflation",
    "public_debt": "fact_public_debt",
}

VALID_PILLARS = frozenset(PILLAR_TABLES.keys())


def get_connection() -> sqlite3.Connection:
    """Return a read-only database connection."""
    if not DATABASE_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database not found. Run 'python main.py --mode etl' first.",
        )
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def validate_pillar(pillar: str) -> str:
    """Validate and return the pillar name."""
    pillar = pillar.lower().strip()
    if pillar not in VALID_PILLARS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown pillar '{pillar}'. Valid: {sorted(VALID_PILLARS)}",
        )
    return pillar


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """API information and available endpoints."""
    return {
        "name": "Portugal Data Intelligence API",
        "version": "2.0.0",
        "data_period": "2010-2025",
        "pillars": sorted(VALID_PILLARS),
        "endpoints": {
            "pillars": "/api/v1/pillars",
            "timeseries": "/api/v1/pillars/{pillar}/timeseries",
            "alerts": "/api/v1/alerts",
            "correlation": "/api/v1/correlation",
            "health": "/api/v1/health",
            "docs": "/docs",
        },
    }


@app.get("/api/v1/health")
def health_check():
    """Health check — verifies database connectivity."""
    try:
        conn = get_connection()
        try:
            row = conn.execute("SELECT COUNT(*) as n FROM dim_date").fetchone()
            return {"status": "healthy", "database": "connected", "date_records": row["n"]}
        finally:
            conn.close()
    except Exception:
        return {"status": "unhealthy", "error": "Database connection failed"}


@app.get("/api/v1/pillars")
def list_pillars():
    """List all available economic pillars with metadata."""
    return {
        "pillars": [
            {
                "key": key,
                "name": cfg["name"],
                "table": cfg["table_name"],
                "granularity": cfg["granularity"],
                "unit": cfg["unit"],
                "description": cfg["description"],
                "sources": cfg["primary_sources"],
            }
            for key, cfg in DATA_PILLARS.items()
        ]
    }


@app.get("/api/v1/pillars/{pillar}")
def get_pillar_latest(pillar: str):
    """Get the latest data point and summary statistics for a pillar."""
    pillar = validate_pillar(pillar)
    table = PILLAR_TABLES[pillar]

    conn = get_connection()
    try:
        df = pd.read_sql(
            f"SELECT d.year, d.month, d.quarter, f.* "
            f"FROM {table} f JOIN dim_date d ON f.date_key = d.date_key "
            f"ORDER BY d.year DESC, d.month DESC LIMIT 1",
            conn,
        )
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for pillar '{pillar}'.")

        # Also get summary stats
        df_all = pd.read_sql(f"SELECT * FROM {table}", conn)
        numeric_cols = df_all.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if c not in ("date_key", "source_key", "id")]

        stats = {}
        for col in numeric_cols:
            series = df_all[col].dropna()
            if series.empty:
                continue
            std_val = series.std()
            stats[col] = {
                "latest": round(float(series.iloc[-1]), 4),
                "mean": round(float(series.mean()), 4),
                "min": round(float(series.min()), 4),
                "max": round(float(series.max()), 4),
                "std": round(float(std_val), 4) if not pd.isna(std_val) else 0.0,
            }
    finally:
        conn.close()

    latest_row = df.iloc[0].to_dict()
    # Clean NaN values for JSON serialization
    latest_row = {k: (None if pd.isna(v) else v) for k, v in latest_row.items()}

    return {
        "pillar": pillar,
        "latest": latest_row,
        "statistics": stats,
        "metadata": DATA_PILLARS.get(pillar, {}),
    }


@app.get("/api/v1/pillars/{pillar}/timeseries")
def get_pillar_timeseries(
    pillar: str,
    start_year: Optional[int] = Query(None, ge=2010, le=2025, description="Start year filter"),
    end_year: Optional[int] = Query(None, ge=2010, le=2025, description="End year filter"),
    columns: Optional[str] = Query(None, description="Comma-separated column names"),
    limit: int = Query(1000, ge=1, le=5000, description="Max rows to return"),
):
    """Get full timeseries data for a pillar with optional filters."""
    pillar = validate_pillar(pillar)
    table = PILLAR_TABLES[pillar]

    conn = get_connection()
    try:
        query = (
            f"SELECT d.year, d.month, d.quarter, d.date_key, f.* "
            f"FROM {table} f JOIN dim_date d ON f.date_key = d.date_key "
        )
        conditions = []
        if start_year:
            conditions.append(f"d.year >= {int(start_year)}")
        if end_year:
            conditions.append(f"d.year <= {int(end_year)}")
        if conditions:
            query += "WHERE " + " AND ".join(conditions) + " "
        query += f"ORDER BY d.year, d.month LIMIT {int(limit)}"

        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    if df.empty:
        return {"pillar": pillar, "count": 0, "data": []}

    # Filter columns if requested
    if columns:
        requested = [c.strip() for c in columns.split(",")]
        keep = ["date_key", "year", "month", "quarter"] + [c for c in requested if c in df.columns]
        df = df[keep]

    # Clean NaN for JSON
    records = df.where(df.notna(), None).to_dict(orient="records")

    return {
        "pillar": pillar,
        "count": len(records),
        "start_year": int(df["year"].min()),
        "end_year": int(df["year"].max()),
        "data": records,
    }


@app.get("/api/v1/alerts")
def get_alerts():
    """Check all indicators against configured thresholds and return active alerts."""
    try:
        from src.alerts.alert_engine import AlertEngine
        engine = AlertEngine()
        alerts = engine.check_all()
        return {
            "total": len(alerts),
            "critical": sum(1 for a in alerts if a.severity == "critical"),
            "warning": sum(1 for a in alerts if a.severity == "warning"),
            "alerts": [
                {
                    "indicator": a.indicator,
                    "description": a.description,
                    "severity": a.severity,
                    "value": a.value,
                    "threshold": a.threshold,
                    "direction": a.direction,
                    "period": a.period,
                }
                for a in alerts
            ],
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Alert check failed")


@app.get("/api/v1/correlation")
def get_correlation():
    """Compute and return cross-pillar Pearson correlation matrix."""
    conn = get_connection()
    try:
        annual_data = {}

        # GDP growth (quarterly → annual average)
        gdp = pd.read_sql(
            "SELECT d.year, f.gdp_growth_yoy FROM fact_gdp f "
            "JOIN dim_date d ON f.date_key = d.date_key", conn
        )
        if not gdp.empty:
            annual_data["GDP Growth"] = gdp.groupby("year")["gdp_growth_yoy"].mean()

        # Unemployment (monthly → annual average)
        unemp = pd.read_sql(
            "SELECT d.year, f.unemployment_rate FROM fact_unemployment f "
            "JOIN dim_date d ON f.date_key = d.date_key", conn
        )
        if not unemp.empty:
            annual_data["Unemployment"] = unemp.groupby("year")["unemployment_rate"].mean()

        # Inflation
        infl = pd.read_sql(
            "SELECT d.year, f.hicp FROM fact_inflation f "
            "JOIN dim_date d ON f.date_key = d.date_key", conn
        )
        if not infl.empty:
            annual_data["Inflation"] = infl.groupby("year")["hicp"].mean()

        # Bond yield
        rates = pd.read_sql(
            "SELECT d.year, f.portugal_10y_bond_yield FROM fact_interest_rates f "
            "JOIN dim_date d ON f.date_key = d.date_key", conn
        )
        if not rates.empty:
            annual_data["Bond Yield 10Y"] = rates.groupby("year")["portugal_10y_bond_yield"].mean()

        # Debt/GDP
        debt = pd.read_sql(
            "SELECT d.year, f.debt_to_gdp_ratio FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key = d.date_key", conn
        )
        if not debt.empty:
            annual_data["Debt/GDP"] = debt.groupby("year")["debt_to_gdp_ratio"].mean()
    finally:
        conn.close()

    if len(annual_data) < 2:
        return {"error": "Insufficient data for correlation analysis."}

    merged = pd.DataFrame(annual_data).dropna()
    corr = merged.corr()

    # Convert to serializable format (replace NaN with None)
    matrix = {}
    for col in corr.columns:
        matrix[col] = {
            row: (round(float(corr.loc[row, col]), 4) if not pd.isna(corr.loc[row, col]) else None)
            for row in corr.index
        }

    return {
        "years_covered": sorted(merged.index.tolist()),
        "indicators": list(corr.columns),
        "correlation_matrix": matrix,
    }
