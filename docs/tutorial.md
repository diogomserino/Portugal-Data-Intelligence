# Project Tutorial

## What Is This Project?

Portugal Data Intelligence is a complete macroeconomic analytics pipeline for the Portuguese economy (2010–2025). It generates realistic synthetic data, processes it through an ETL pipeline, runs statistical analysis, produces narrative insights, and delivers everything via Power BI dashboards, an interactive Streamlit dashboard, and self-contained HTML reports.

Think of it as what a consulting engagement might produce — except fully automated, from raw data to final deliverable, in a single command.

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip (comes with Python)

### Setup

```bash
# Clone and enter the project
git clone <repo-url>
cd portugal-data-intelligence

# Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# For development (tests, linting, type checking)
pip install -r requirements-dev.txt
```

### Running the Pipeline

```bash
# Run everything end-to-end
python main.py

# Or pick a specific stage
python main.py --mode etl        # Generate data + load into database
python main.py --mode analysis   # Statistical analysis + charts
python main.py --mode reports    # AI insights + executive briefing
python main.py --mode quick      # ETL + analysis (skip reports)

# See all available modes
python main.py --list
```

---

## The Pipeline, Step by Step

The project follows a linear flow. Each stage produces outputs that feed into the next.

```
Generate Data → Extract → Transform → Load → Analyse → Insights → Reports
```

Let's walk through each stage.

---

### Step 1: Generate Synthetic Data

**Files:** `src/etl/generate_data.py`, `src/etl/generate_eu_benchmark.py`

Since we can't redistribute real data from INE or Banco de Portugal, the project generates **realistic synthetic data** instead. This isn't random noise — it's built from actual reference points (e.g., Portugal's real GDP trajectory, the 2011–2014 sovereign debt crisis, the 2020 COVID shock) and interpolated to monthly or quarterly resolution with controlled noise and seasonal patterns.

The generator creates data for **six macroeconomic pillars**:

| Pillar | Granularity | What It Covers |
|--------|-------------|----------------|
| GDP | Quarterly | Nominal/real GDP, growth rates (derived from real GDP), per capita |
| Unemployment | Monthly | Total, youth, long-term rates, labour force participation |
| Credit | Monthly | Total lending, corporate, household, NPL ratio |
| Interest Rates | Monthly | ECB rate, Euribor (3M/6M/12M), PT 10Y bond yield |
| Inflation | Monthly | HICP, CPI (estimated from HICP), core inflation, energy/food components |
| Public Debt | Quarterly | Total debt, debt-to-GDP, budget balance, budget deficit (rolling annual), external share (estimated) |

A separate generator (`generate_eu_benchmark.py`) creates comparison data for Germany, Spain, France, Italy, and EU/Euro Area averages — used later for benchmarking Portugal against its peers.

**Output:** CSV files in `data/raw/`

---

### Step 2: ETL — Extract, Transform, Load

**Files:** `src/etl/extract.py` → `src/etl/transform.py` → `src/etl/load.py`
**Orchestrator:** `src/etl/pipeline.py`

This is a classic ETL pipeline split into three modules:

#### Extract (`extract.py`)
Reads the raw CSV files from `data/raw/` and returns pandas DataFrames. Each pillar has its own extraction function (`extract_gdp()`, `extract_unemployment()`, etc.), plus a convenience `extract_all()` that returns everything as a dictionary.

#### Transform (`transform.py`)
Cleans and standardises the raw data:
- Renames columns to match the database schema
- Derives temporal keys (`2015-Q2` for quarterly, `2015-06` for monthly)
- Validates data ranges (e.g., unemployment rate between 0–50%) and clips outliers with warnings
- Calculates derived fields where needed (growth rates derived from real GDP, rolling averages, `budget_deficit_annual` as rolling 4-quarter average)
- Flags projected or preliminary data rows with the `is_provisional` column across all fact tables
- Marks estimated columns explicitly: `cpi_estimated` (derived from HICP, not real INE CPI data) and `external_debt_share_estimated` (not sourced from an API)
- Saves processed data to `data/processed/`

#### Load (`load.py`)
Populates a SQLite database using a **star schema** (see the Database section below):
- Runs the DDL scripts to create tables (`sql/ddl/create_tables.sql`)
- Seeds dimension tables (`sql/ddl/seed_dimensions.sql`)
- Inserts fact data with foreign key resolution and conflict handling

#### Pipeline Orchestrator (`pipeline.py`)
Chains all three steps together. Can run the full pipeline or individual stages via `--step extract|transform|load|all`. Prints a summary table showing row counts per pillar at each stage.

**Output:** Populated SQLite database at `data/database/portugal_data_intelligence.db`

---

### Step 3: Statistical Analysis

**Files:** Everything in `src/analysis/`

This is where the data gets analysed. There are several specialised modules:

#### `statistical_analysis.py` — Descriptive Statistics
Runs per-pillar analysis: mean, median, standard deviation, skewness, trend classification (increasing/decreasing/stable), and identifies notable periods (crisis impacts, COVID effects). The main entry point is `run_all_analyses()`.

#### `correlation_analysis.py` — Cross-Pillar Relationships
Examines how the six pillars relate to each other:
- **Correlation matrix** across all monthly indicators
- **Phillips curve** analysis (unemployment vs inflation)
- **Interest rate transmission** — how ECB rate changes flow through to credit and inflation (with lag analysis at 0, 3, 6, 12 months)
- **Debt-GDP dynamics** — how debt and GDP interact

Uses Pearson correlation with p-values, and flags suspiciously high correlations (|r| > 0.95).

#### `benchmarking.py` — Portugal vs EU Peers
Compares Portugal against Germany, Spain, France, Italy, and EU/EA averages across five indicators. Calculates rankings, gaps to EU average, convergence/divergence trends.

#### `forecasting.py` — 3-Year Projections
Projects each indicator forward to 2026–2028 using:
- Log-linear trend extrapolation (for GDP, credit)
- Exponential smoothing (for noisy series)
- Mean-reversion / Ornstein-Uhlenbeck (for rates and ratios)

Includes 68% and 95% confidence bands. No heavy dependencies — just numpy and scipy.

#### `significance_tests.py` — Inferential Statistics
Adds statistical rigour: trend significance via OLS regression, period comparison via ANOVA, structural break detection, and lagged correlation significance testing.

#### `visualisations.py` — Chart Generation
Produces publication-quality PNG charts (300 DPI) for all pillars. Charts include economic period background shading (pre-crisis, troika, recovery, COVID, post-COVID) and a consistent professional style.

**Output:** Analysis results (dicts/JSON) + PNG charts in `reports/powerbi/charts/`

---

### Step 4: AI Insights

**Files:** `src/ai_insights/insight_engine.py`, `src/ai_insights/generate_insights.py`

The `InsightEngine` class connects to the database, pulls statistical data, and generates executive-level narratives for each pillar:
- **Headline** — one-liner summary
- **Executive summary** — multi-paragraph narrative
- **Key findings** — bulleted insights
- **Recommendations**
- **Cross-pillar insights** — how indicators relate to each other

It works in **two modes**:
- **Rule-based** (default): Uses templates and statistical thresholds. No API key needed — works offline.
- **AI-powered** (optional): Sends data to GPT-4 for richer narratives. Requires `OPENAI_API_KEY` in your environment.

**Output:** JSON files in `reports/insights/`

---

### Step 5: Reports & Delivery

Reports are delivered through three channels:

#### HTML Report (`dashboard/generate_report.py`)
Generates a self-contained Big4-style HTML briefing with:
- KPI dashboard with all six pillar metrics
- Per-pillar sections with embedded charts (base64 data URIs)
- EU benchmark analysis
- Risk matrix and recommendations
- Fully portable — single file, no external dependencies

#### Interactive Dashboard (`dashboard/app.py`)
Streamlit-based web dashboard with:
- Executive overview with real-time KPI cards
- Pillar deep-dive with configurable filters
- Cross-pillar correlation analysis and Phillips curve
- Raw data explorer with CSV download

#### REST API (`api/main.py`)
FastAPI endpoints for programmatic access:
- `/api/v1/pillars` — list all economic pillars
- `/api/v1/pillars/{pillar}/timeseries` — filtered data queries
- `/api/v1/alerts` — active threshold alerts
- `/api/v1/correlation` — cross-pillar correlation matrix

**Output:** JSON briefings in `reports/insights/`, HTML report, live dashboard

---

## The Database

The SQLite database uses a **star schema** — a common pattern in analytics where you have:

- **Dimension tables** (the "who/when/where"): `dim_date` (192 monthly rows from Jan 2010 to Dec 2025) and `dim_source` (5 data sources)
- **Fact tables** (the "what happened"): one per pillar (`fact_gdp`, `fact_unemployment`, `fact_credit`, `fact_interest_rates`, `fact_inflation`, `fact_public_debt`) plus `fact_eu_benchmark` for peer comparison

Each fact row links to a date via `date_key` and to a source via `source_key`. This makes it easy to slice data by time period or source.

**Notable schema details:**

- All fact tables include an `is_provisional` boolean column that flags rows containing projected or preliminary data.
- In `fact_inflation`, the column `cpi_estimated` (not `cpi`) makes it clear that CPI values are estimated from HICP rather than sourced directly from INE.
- In `fact_public_debt`, `external_debt_share_estimated` (not `external_debt_share`) signals that this field is an estimate, not fetched from an API. The table also includes `budget_deficit_annual`, a rolling 4-quarter average of the budget balance.
- In `fact_gdp`, growth rates (`gdp_growth_yoy`, `gdp_growth_qoq`) are derived from the `real_gdp` column during the transform step, rather than pulled from the API (previous versions reflected nominal growth).

The DDL lives in `sql/ddl/` and there are 7 pre-written analytical queries in `sql/queries/` (one per pillar plus a cross-pillar analysis).

---

## Configuration

### `config/settings.py`
The central hub for all project settings:
- **Paths**: where raw data, processed data, database, reports, and logs live
- **Database config**: SQLite pragmas (WAL mode, 64MB cache, foreign keys)
- **Date ranges**: `START_YEAR=2010`, `END_YEAR=2025`
- **Pillar definitions**: the 6 macroeconomic pillars with their granularity, units, and sources
- **OpenAI config**: model and API settings for AI insights (optional)
- **`ensure_directories()`**: creates all required folders on first run

### `config/data_sources.json`
Metadata for the 5 external data sources (INE, Banco de Portugal, PORDATA, Eurostat, ECB) — their URLs, API endpoints, supported formats, and which indicators they provide.

---

## Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=src

# Individual test files
pytest tests/test_etl.py        # ETL pipeline tests
pytest tests/test_analysis.py   # Analysis module tests
pytest tests/test_insights.py   # Insight generation tests
```

The tests verify:
- **ETL**: raw files exist, correct row counts (64 quarterly / 192 monthly), column names match schema, data types and ranges are valid
- **Analysis**: all pillars are analysed, correlation matrix is square with values in [-1, 1], no spurious perfect correlations
- **Insights**: insight generation produces valid structured output

Shared fixtures live in `tests/conftest.py`.

---

## Project Structure at a Glance

```
portugal-data-intelligence/
│
├── main.py                          # Entry point — orchestrates the full pipeline
├── config/
│   ├── settings.py                  # All paths, DB config, pillar definitions
│   └── data_sources.json            # External source metadata
│
├── src/
│   ├── etl/
│   │   ├── generate_data.py         # Synthetic data generation (6 pillars)
│   │   ├── generate_eu_benchmark.py # EU benchmark data generation
│   │   ├── extract.py               # Read raw CSVs → DataFrames
│   │   ├── transform.py             # Clean, validate, standardise
│   │   ├── load.py                  # Populate SQLite database
│   │   └── pipeline.py              # ETL orchestrator
│   │
│   ├── analysis/
│   │   ├── statistical_analysis.py  # Descriptive stats per pillar
│   │   ├── correlation_analysis.py  # Cross-pillar relationships
│   │   ├── benchmarking.py          # Portugal vs EU peers
│   │   ├── forecasting.py           # 3-year projections
│   │   ├── significance_tests.py    # Inferential statistics
│   │   ├── visualisations.py        # Chart generation (300 DPI PNGs)
│   │   └── run_analysis.py          # Analysis orchestrator
│   │
│   ├── ai_insights/
│   │   ├── insight_engine.py        # Rule-based + AI narrative generation
│   │   └── generate_insights.py     # CLI for generating insights
│   │
│   ├── reporting/
│   │   └── shared_styles.py         # Shared colour palette and fonts
│   │
│   └── utils/
│       └── logger.py                # Centralised logging (console + file)
│
├── reports/                         # Generated outputs only
│   └── powerbi/
│       ├── charts/                  # Generated PNG charts
│       ├── dax_measures.md          # Power BI DAX definitions
│       └── dashboard_specification.md
│
├── sql/
│   ├── ddl/                         # CREATE TABLE + seed scripts
│   └── queries/                     # 7 analytical SQL queries
│
├── data/
│   ├── raw/                         # Generated CSV files
│   ├── processed/                   # Cleaned CSV files
│   └── database/                    # SQLite database
│
├── tests/                           # pytest test suite
├── notebooks/                       # Jupyter notebooks
├── docs/                            # Documentation
└── logs/                            # Application logs
```

---

## Where to Go Next

- **Want to explore the data interactively?** Open `notebooks/01_exploratory_analysis.ipynb`
- **Want to understand the database schema?** Read `docs/data_dictionary.md`
- **Want to see the system architecture?** Read `docs/architecture.md`
- **Want to add a new data pillar?** Add its config to `DATA_PILLARS` in `config/settings.py`, create the corresponding ETL functions, and follow the existing pattern
- **Want to use real AI insights?** Set `OPENAI_API_KEY` in your environment and run with `--mode reports`
