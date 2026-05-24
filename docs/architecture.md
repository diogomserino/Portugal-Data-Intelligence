# Architecture Document

## Portugal Data Intelligence - System Architecture

**Version:** 2.2
**Last Updated:** May 2026
**Status:** Phase 3 - Production

---

## 1. System Overview

Portugal Data Intelligence is a modular, pipeline-driven analytics platform designed to
ingest macroeconomic data from multiple Portuguese and European statistical authorities,
transform it into a unified analytical schema, and produce AI-augmented insights delivered
through multiple reporting channels.

### High-Level Architecture Diagram

```
+===========================================================================+
|                     PORTUGAL DATA INTELLIGENCE                            |
+===========================================================================+
|                                                                           |
|  +-------------------+    +-------------------+    +-------------------+  |
|  |   DATA SOURCES    |    |   ETL PIPELINE    |    |   DATA STORE     |  |
|  |                   |    |                   |    |                   |  |
|  |  INE              |--->|  1. Extract       |--->|  SQLite Database  |  |
|  |  Banco de Portugal|    |  2. Validate      |    |                   |  |
|  |  Eurostat         |    |  3. Transform     |    |  2 dim tables     |  |
|  |  ECB SDW          |    |  4. Enrich        |    |  12 fact tables   |  |
|  |                   |    |  5. Load          |    |  lineage tables   |  |
|  +-------------------+    +-------------------+    +--------+----------+  |
|                                                             |             |
|            +------------------------------------------------+             |
|            |                                                              |
|            v                                                              |
|  +-------------------+    +-------------------+    +-------------------+  |
|  | ANALYSIS ENGINE   |    |  AI INSIGHTS      |    |  DELIVERY LAYER  |  |
|  |                   |    |                   |    |                   |  |
|  | - Trend Analysis  |--->| - Rule-based      |--->| - Power BI       |  |
|  | - Correlations    |    |   Narrative       |    | - Streamlit      |  |
|  | - SARIMAX Forecast|    | - Anomaly Alerts  |    | - HTML Report    |  |
|  | - VAR / VECM      |    | - Key Findings    |    |   (Plotly)       |  |
|  | - Nowcasting      |    | - Recommendations |    | - REST API       |  |
|  | - Anomaly Detect  |    |                   |    | - Excel Export   |  |
|  | - NUTS2 Choropleth|    |                   |    | - NUTS2 Maps     |  |
|  +-------------------+    +-------------------+    +-------------------+  |
|                                                                           |
+===========================================================================+
```

---

## 2. Data Flow

The platform processes data through six sequential stages. Each stage is independently
executable and produces artefacts that serve as inputs to the next stage.

### Pipeline Stages

```
+----------+    +-----------+    +------+    +---------+    +---------+    +--------+
|          |    |           |    |      |    |         |    |         |    |        |
| EXTRACT  |--->| TRANSFORM |--->| LOAD |--->| ANALYSE |--->| INSIGHT |--->| REPORT |
|          |    |           |    |      |    |         |    |         |    |        |
+----------+    +-----------+    +------+    +---------+    +---------+    +--------+
     |               |              |             |              |              |
     v               v              v             v              v              v
  Raw CSV/       Cleaned &      SQLite DB    Statistical    AI-Generated   Power BI,
  Excel files    validated      populated    results &      narratives &   Streamlit,
  in data/raw/   DataFrames     with fact    correlation    commentary     HTML, API
                 in data/       & dimension  matrices
                 in data/       & dimension  matrices
                 processed/     tables
```

### Stage Descriptions

#### Stage 1: Extract
- Ingest raw data files from CSV, Excel, and JSON formats
- Support for both file-based and API-based extraction
- Raw files stored in `data/raw/` with source metadata

#### Stage 2: Transform
- Data validation: null checks, type enforcement, range validation
- Standardisation: consistent date formats, currency units, naming conventions
- Enrichment: calculated fields (e.g., YoY growth, moving averages)
- Output stored in `data/processed/` as cleaned CSV files

#### Stage 3: Load
- Populate SQLite database with dimension and fact tables
- Apply referential integrity constraints
- Create analytical indices for query performance
- Database stored at `data/database/portugal_data_intelligence.db`

#### Stage 4: Analyse
- Time series decomposition (trend, seasonal, residual)
- Cross-pillar correlation analysis and Granger causality
- Year-on-year and quarter-on-quarter comparisons
- SARIMAX forecasting with cached model persistence (7-day TTL)
- VAR / VECM for multi-variable dynamics (IRF, FEVD)
- Bridge-equation nowcasting for in-quarter GDP estimation
- Rolling z-score and Isolation Forest anomaly detection
- Regional NUTS2 analysis with Plotly choropleth

#### Stage 5: Insight
- Feed analytical results to OpenAI GPT-4 for narrative generation
- Produce structured commentary for each data pillar
- Identify anomalies and provide contextual explanations
- Generate executive-level summary findings

#### Stage 6: Deliver
- Power BI dashboard with KPIs, drill-downs, and what-if scenarios
- Interactive Streamlit dashboard (open-source alternative)
- Self-contained HTML briefing report with embedded Plotly charts
- REST API for programmatic data access (FastAPI)
- Excel workbook export with one sheet per pillar (`python main.py --mode excel`)
- Interactive NUTS2 choropleth map embedded in HTML report

---

## 3. Data Model Overview

The database follows a star schema design with shared dimension tables and
pillar-specific fact tables.

### Entity Relationship Summary

```
                        +------------------+
                        |   dim_date       |
                        |------------------|
                        | date_key (PK)    |
                        | full_date        |
                        | year             |
                        | quarter          |
                        | month            |
                        | month_name       |
                        | is_quarter_end   |
                        +--------+---------+
                                 |
          +----------------------+----------------------+
          |          |           |           |          |
          v          v           v           v          v
  +-------+--+ +----+-----+ +--+-------+ +-+--------+ +--+--------+
  | fact_gdp | | fact_    | | fact_    | | fact_    | | fact_     |
  |          | | unemploy | | credit   | | interest | | inflation |
  | date_key | | date_key | | date_key | | date_key | | date_key  |
  | nominal  | | rate     | | total    | | ecb_rate | | hicp      |
  | real     | | youth    | | nfc      | | euribor  | | cpi_est   |
  | growth   | | lfp_rate | | house    | | bond_10y | | core      |
  | is_prov  | | is_prov  | | is_prov  | | is_prov  | | is_prov   |
  +----------+ +----------+ +----------+ +----------+ +-----------+

                                 +
                                 |
                        +--------+---------+
                        | fact_public_debt |
                        |------------------|
                        | date_key         |
                        | total_debt       |
                        | debt_to_gdp      |
                        | budget_deficit   |
                        | budget_def_ann   |
                        | ext_debt_est     |
                        | is_provisional   |
                        +------------------+

  +------------------+
  | dim_source       |
  |------------------|
  | source_key (PK)  |
  | source_name      |
  | source_url       |
  | description      |
  +------------------+
```

### Table Inventory

| Table | Type | Granularity | Description |
|-------|------|-------------|-------------|
| `dim_date` | Dimension | N/A | Calendar dimension with year, quarter, month attributes |
| `dim_source` | Dimension | N/A | Data source reference table |
| `fact_gdp` | Fact | Quarterly | GDP metrics: nominal, real, growth rate, per capita |
| `fact_unemployment` | Fact | Monthly | Unemployment rate, youth unemployment, labour force participation |
| `fact_credit` | Fact | Monthly | Bank lending: total, non-financial corporations, households |
| `fact_interest_rates` | Fact | Monthly | ECB rate, Euribor (3M/6M/12M), 10-year bond yield |
| `fact_inflation` | Fact | Monthly | HICP, CPI (estimated), core inflation |
| `fact_public_debt` | Fact | Quarterly | Total debt, debt-to-GDP ratio, budget deficit, external debt share |
| `fact_housing` | Fact | Annual | House price index (2015=100), transactions, avg €/m², mortgage lending |
| `fact_labor_detail` | Fact | Annual | Employment by sector (services/industry/agriculture), real wage index, productivity |
| `fact_external_accounts` | Fact | Quarterly | Current account % GDP, trade balance, REER, ULC, export growth |
| `fact_fiscal` | Fact | Annual | Revenue/expenditure % GDP, health/education/social/interest breakdown |
| `fact_inequality` | Fact | Annual | Gini index, S80/S20 ratio, poverty risk rate, median income index |
| `fact_regional` | Fact | Annual × 7 | NUTS2 regional data: GDP per capita PPS, EU27 index, unemployment by region |

---

## 4. Tech Stack Justification

### Python 3.10+
Selected as the primary language for its mature data science ecosystem, extensive library
support, and widespread adoption in analytics and data engineering. Python provides the
glue between all layers of the platform.

### SQLite 3
Chosen as the database engine for its zero-configuration deployment, file-based portability,
and full SQL support. For a project of this scale (approximately 15 years of monthly/quarterly/annual
data across 12 pillars + NUTS2 regional data), SQLite provides more than adequate performance whilst remaining
easily distributable as a single file. No server infrastructure is required.

### pandas / NumPy
The de facto standard for tabular data manipulation in Python. pandas provides expressive
DataFrame operations for ETL transformations, whilst NumPy underpins all numerical
computations and serves as the foundation for scipy and scikit-learn.

### matplotlib / seaborn / Plotly
A layered visualisation strategy: matplotlib for publication-quality static charts, seaborn
for statistical visualisations with minimal code, and Plotly for interactive dashboards
and HTML-embeddable charts.

### scikit-learn / SciPy
SciPy provides statistical testing and time series decomposition capabilities, whilst
scikit-learn supports regression modelling, clustering, and simple forecasting tasks.

### OpenAI GPT-4 API
Used to generate natural-language narratives from structured analytical outputs. The AI
layer transforms statistical findings into executive-readable commentary, reducing the
manual effort required for report writing.

### Streamlit / FastAPI
Streamlit provides an interactive, open-source dashboard alternative to Power BI.
FastAPI exposes macroeconomic data via a REST API for programmatic integration.

### Power BI
Selected as the interactive dashboard platform due to its enterprise prevalence,
particularly in Big Four and corporate advisory contexts. The project provides data
model specifications and DAX measure definitions for Power BI implementation.

---

## 5. Security and Data Governance

- **API keys** are stored in environment variables, never committed to source control
- **`.gitignore`** excludes all data files, database files, and generated reports
- **Real API data** is fetched from Eurostat, ECB, and Banco de Portugal; synthetic fallback is available for offline development
- **Logging** captures all pipeline operations for auditability

---

## 6. Extensibility

The modular architecture supports several natural extensions:

- **Additional data pillars** (e.g., trade balance, foreign direct investment)
- **Alternative databases** (PostgreSQL, DuckDB) via connection string change
- **Real-time data feeds** through API-based extraction
- **Additional AI models** (e.g., local LLMs, additional API providers)
- **Web dashboard** using Dash or similar as an alternative to Power BI
