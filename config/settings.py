"""
Portugal Data Intelligence - Central Configuration
====================================================
All project-wide settings, paths, constants, and configuration parameters.
"""

import logging
import os
from pathlib import Path

# =============================================================================
# PATH DEFINITIONS
# =============================================================================

# Project root directory (two levels up from this config file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DATABASE_DIR = DATA_DIR / "database"

# Source code directories
SRC_DIR = PROJECT_ROOT / "src"
ETL_DIR = SRC_DIR / "etl"
ANALYSIS_DIR = SRC_DIR / "analysis"
AI_INSIGHTS_DIR = SRC_DIR / "ai_insights"
UTILS_DIR = SRC_DIR / "utils"

# SQL directories
SQL_DIR = PROJECT_ROOT / "sql"
DDL_DIR = SQL_DIR / "ddl"
QUERIES_DIR = SQL_DIR / "queries"

# Output directories
REPORTS_DIR = PROJECT_ROOT / "reports"
POWERBI_DIR = REPORTS_DIR / "powerbi"
# POWERPOINT_DIR removed in v2 — reports delivered via Power BI, Streamlit, HTML
INSIGHTS_DIR = REPORTS_DIR / "insights"
CHARTS_DIR = POWERBI_DIR / "charts"

# Dashboard directories
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DASHBOARD_PAGES_DIR = DASHBOARD_DIR / "pages"

# Other directories
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
TESTS_DIR = PROJECT_ROOT / "tests"
DOCS_DIR = PROJECT_ROOT / "docs"
CONFIG_DIR = PROJECT_ROOT / "config"

# =============================================================================
# DATABASE SETTINGS
# =============================================================================

DATABASE_NAME = "portugal_data_intelligence.db"
DATABASE_PATH = DATABASE_DIR / DATABASE_NAME
# SQLite pragmas for performance
SQLITE_PRAGMAS = {
    "journal_mode": "WAL",
    "cache_size": -64000,  # 64 MB cache
    "foreign_keys": 1,
    "synchronous": "NORMAL",
}

# =============================================================================
# DATE RANGE CONSTANTS
# =============================================================================

START_YEAR = 2010
END_YEAR = 2025

# Quarterly range (for GDP, Public Debt)
QUARTERLY_START = "2010-Q1"
QUARTERLY_END = "2025-Q4"

# Monthly range (for Unemployment, Credit, Interest Rates, Inflation)
MONTHLY_START = "2010-01"
MONTHLY_END = "2025-12"

# =============================================================================
# DATA PILLAR DEFINITIONS
# =============================================================================

DATA_PILLARS = {
    "gdp": {
        "name": "Gross Domestic Product",
        "table_name": "fact_gdp",
        "granularity": "quarterly",
        "unit": "EUR millions",
        "description": "Nominal and real GDP, growth rates, and GDP per capita",
        "primary_sources": ["INE", "Eurostat"],
    },
    "unemployment": {
        "name": "Unemployment",
        "table_name": "fact_unemployment",
        "granularity": "monthly",
        "unit": "percentage",
        "description": "Unemployment rate, youth unemployment, and labour force participation",
        "primary_sources": ["INE", "Eurostat"],
    },
    "credit": {
        "name": "Credit to the Economy",
        "table_name": "fact_credit",
        "granularity": "monthly",
        "unit": "EUR millions",
        "description": "Bank lending to non-financial corporations and households",
        "primary_sources": ["Banco de Portugal"],
    },
    "interest_rates": {
        "name": "Interest Rates",
        "table_name": "fact_interest_rates",
        "granularity": "monthly",
        "unit": "percentage",
        "description": "ECB key rates, Euribor, and Portuguese sovereign bond yields",
        "primary_sources": ["Banco de Portugal", "ECB"],
    },
    "inflation": {
        "name": "Inflation",
        "table_name": "fact_inflation",
        "granularity": "monthly",
        "unit": "percentage",
        "description": "HICP, CPI, and core inflation metrics",
        "primary_sources": ["INE", "Eurostat"],
    },
    "public_debt": {
        "name": "Public Debt",
        "table_name": "fact_public_debt",
        "granularity": "quarterly",
        "unit": "EUR millions / percentage of GDP",
        "description": "General government debt, debt-to-GDP ratio, and debt composition",
        "primary_sources": ["Banco de Portugal", "PORDATA"],
    },
}

# =============================================================================
# CRISIS PERIODS (single source of truth)
# =============================================================================

CRISIS_PERIODS = {
    "sovereign_debt_crisis": {"years": (2011, 2014), "label": "Sovereign Debt Crisis"},
    "covid_pandemic": {"years": (2020, 2021), "label": "COVID-19 Pandemic"},
    "energy_crisis": {"years": (2022, 2023), "label": "Energy and Inflation Crisis"},
}

# Chart-friendly period definitions (includes pre/post crisis context)
CHART_PERIODS = {
    "Pre-crisis": ("2010", "2011"),
    "Troika": ("2012", "2014"),
    "Recovery": ("2015", "2019"),
    "COVID": ("2020", "2020"),
    "Post-COVID": ("2021", "2025"),
}

# =============================================================================
# DATA SOURCE URLS
# =============================================================================

DATA_SOURCES = {
    "INE": "https://www.ine.pt",
    "Banco de Portugal": "https://bpstat.bportugal.pt",
    "PORDATA": "https://www.pordata.pt",
    "Eurostat": "https://ec.europa.eu/eurostat",
    "ECB": "https://www.ecb.europa.eu/stats",
}

# =============================================================================
# DATA QUALITY SETTINGS
# =============================================================================

DQ_FAIL_ON_ERROR = os.environ.get("DQ_FAIL_ON_ERROR", "").lower() in ("1", "true", "yes")

DATA_QUALITY_DIR = REPORTS_DIR / "data_quality"

# Plausible ranges for data validation (pillar -> column -> (min, max))
DATA_RANGES = {
    "unemployment": {
        "unemployment_rate": (0, 20),
        "youth_unemployment_rate": (0, 60),
        "long_term_unemployment_rate": (0, 30),
        "labour_force_participation_rate": (40, 100),
    },
    "gdp": {
        "gdp_growth_yoy": (-16, 18),
        "gdp_growth_qoq": (-16, 18),
        "nominal_gdp": (20000, 80000),
        "gdp_per_capita": (10000, 35000),
    },
    "inflation": {
        "hicp": (-2, 12),
        "cpi_estimated": (-2, 12),
        "core_inflation": (-2, 10),
    },
    "public_debt": {
        "debt_to_gdp_ratio": (50, 160),
        "budget_deficit": (-15, 5),
        "budget_deficit_annual": (-15, 5),
        "external_debt_share_estimated": (20, 80),
    },
    "credit": {
        "total_credit": (500000, 1000000),
        "npl_ratio": (0, 20),
    },
    "interest_rates": {
        "ecb_main_refinancing_rate": (-1, 6),
        "euribor_3m": (-1, 6),
        "portugal_10y_bond_yield": (-1, 18),
    },
}

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "portugal_data_intelligence.log"
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# =============================================================================
# AI INSIGHTS CONFIGURATION
# =============================================================================

OPENAI_MODEL = "gpt-4"
OPENAI_MAX_TOKENS = 2000
OPENAI_TEMPERATURE = 0.3  # Low temperature for factual, analytical outputs

# =============================================================================
# REPORT SETTINGS
# =============================================================================

REPORT_AUTHOR = "Portugal Data Intelligence"

# API / CORS
API_ALLOWED_ORIGINS = os.environ.get(
    "API_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8501"
).split(",")
API_KEY = os.environ.get("API_KEY", "")  # empty = no auth required
REPORT_LANGUAGE = "en-GB"
REPORT_DATE_FORMAT = "%d %B %Y"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def ensure_directories():
    """Create all required project directories if they do not exist."""
    directories = [
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        DATABASE_DIR,
        ETL_DIR,
        ANALYSIS_DIR,
        AI_INSIGHTS_DIR,
        UTILS_DIR,
        DDL_DIR,
        QUERIES_DIR,
        POWERBI_DIR,
        CHARTS_DIR,
        INSIGHTS_DIR,
        DASHBOARD_PAGES_DIR,
        NOTEBOOKS_DIR,
        TESTS_DIR,
        DOCS_DIR,
        LOG_DIR,
        DATA_QUALITY_DIR,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def get_pillar_names():
    """Return a list of all data pillar identifiers."""
    return list(DATA_PILLARS.keys())


def get_pillar_config(pillar_key):
    """Return the configuration dictionary for a given data pillar."""
    return DATA_PILLARS.get(pillar_key)
