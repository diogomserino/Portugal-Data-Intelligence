# Data Dictionary

## Portugal Data Intelligence - Complete Data Dictionary

**Version:** 2.0
**Last Updated:** 26 March 2026
**Source of truth:** `sql/ddl/create_tables.sql`

---

## Overview

This document defines every table, column, data type, and constraint in the Portugal
Data Intelligence database. The schema follows a star schema design with shared dimension
tables and six pillar-specific fact tables.

> **This dictionary is generated from the DDL.** If it ever diverges from `sql/ddl/create_tables.sql`, the DDL is authoritative.

---

## Numeric Conventions

All downstream consumers (including Power BI DAX measures) should observe these conventions:

- **Percentages** are stored as actual percentage values -- e.g., `6.2` means 6.2%, **not** 0.062.
- **Monetary values** are denominated in **EUR millions** unless otherwise noted in the column description.
- **Rates** (interest rates, growth rates) are expressed in **percentage points** -- e.g., `1.50` means 1.50 pp.

---

## Date Key Format

The database uses **TEXT-based date keys** with mixed granularity:

- **Monthly pillars** (unemployment, credit, interest_rates, inflation): `'YYYY-MM'` (e.g., `'2023-06'`)
- **Quarterly pillars** (gdp, public_debt): `'YYYY-QN'` (e.g., `'2023-Q2'`)

When joining quarterly and monthly tables, convert quarterly keys to the quarter-end month:

```sql
CASE SUBSTR(q.date_key, 6, 1)
  WHEN '1' THEN SUBSTR(q.date_key, 1, 4) || '-03'
  WHEN '2' THEN SUBSTR(q.date_key, 1, 4) || '-06'
  WHEN '3' THEN SUBSTR(q.date_key, 1, 4) || '-09'
  WHEN '4' THEN SUBSTR(q.date_key, 1, 4) || '-12'
END
```

---

## Dimension Tables

### dim_date

The calendar dimension table, providing temporal attributes for all fact table joins.

| Column | Data Type | Nullable | Description |
|--------|-----------|----------|-------------|
| `date_key` | TEXT | No (PK) | `'YYYY-MM'` for monthly rows, `'YYYY-QN'` for quarterly rows |
| `full_date` | TEXT | No | ISO date `'YYYY-MM-DD'` (first day of month, or last day of quarter) |
| `year` | INTEGER | No | Calendar year (2010-2030). CHECK constraint. |
| `quarter` | INTEGER | No | Calendar quarter (1-4). CHECK constraint. |
| `month` | INTEGER | No | Calendar month (1-12). CHECK constraint. |
| `month_name` | TEXT | No | Full month name (e.g., 'January') |
| `is_quarter_end` | INTEGER | No | Flag: 1 if last month of quarter (Mar, Jun, Sep, Dec), else 0 |

**Granularity:** 192 monthly rows (2010-01 to 2025-12) + 64 quarterly rows (2010-Q1 to 2025-Q4) = 256 rows total.

---

### dim_source

Reference table for institutional data providers.

| Column | Data Type | Nullable | Description |
|--------|-----------|----------|-------------|
| `source_key` | INTEGER | No (PK) | Auto-increment surrogate key |
| `source_name` | TEXT | No (UQ) | Full name of the data source (e.g., 'INE', 'Banco de Portugal') |
| `source_url` | TEXT | Yes | Official website URL |
| `description` | TEXT | Yes | Brief description of the source |

**Granularity:** 5 rows (INE, Banco de Portugal, PORDATA, Eurostat, ECB).

---

## Fact Tables

### Pillar 1: fact_gdp

**Granularity:** Quarterly (2010-Q1 to 2025-Q4 = 64 rows)
**Primary Sources:** Eurostat SDMX (`namq_10_gdp`, `nama_10_pc`)

| Column | Data Type | Nullable | Unit | Constraints | Description |
|--------|-----------|----------|------|-------------|-------------|
| `id` | INTEGER | No (PK) | - | AUTOINCREMENT | Surrogate key |
| `date_key` | TEXT | No (FK) | - | FK → dim_date | Quarter key (e.g., `'2023-Q2'`) |
| `nominal_gdp` | REAL | No | EUR millions | NOT NULL | Gross Domestic Product at current prices |
| `real_gdp` | REAL | Yes | EUR millions | | GDP at constant prices (base year 2015) |
| `gdp_growth_yoy` | REAL | Yes | % | [-50, 50] | Year-on-year growth rate — **derived from real_gdp** during transform |
| `gdp_growth_qoq` | REAL | Yes | % | [-30, 30] | Quarter-on-quarter growth rate — **derived from real_gdp** during transform |
| `gdp_per_capita` | REAL | Yes | EUR | >= 0 | GDP per capita (annualised nominal GDP / population) |
| `is_provisional` | INTEGER | No | boolean | {0, 1} | 1 = provisional/projected data, 0 = confirmed |
| `source_key` | INTEGER | No (FK) | - | FK → dim_source | Data source reference |
| `created_at` | TEXT | No | timestamp | DEFAULT CURRENT_TIMESTAMP | Row creation timestamp |

**Unique constraint:** (`date_key`, `source_key`)

---

### Pillar 2: fact_unemployment

**Granularity:** Monthly (Jan 2010 to Dec 2025 = 192 rows)
**Primary Sources:** Eurostat SDMX (`une_rt_m`, `une_ltu_q`, `lfsq_argan`)

| Column | Data Type | Nullable | Unit | Constraints | Description |
|--------|-----------|----------|------|-------------|-------------|
| `id` | INTEGER | No (PK) | - | AUTOINCREMENT | Surrogate key |
| `date_key` | TEXT | No (FK) | - | FK → dim_date | Month key (e.g., `'2023-06'`) |
| `unemployment_rate` | REAL | No | % | [0, 50] | Total unemployment rate (ILO definition) |
| `youth_unemployment_rate` | REAL | Yes | % | [0, 80] | Unemployment rate for ages 15-24 |
| `long_term_unemployment_rate` | REAL | Yes | % | [0, 50] | Unemployment > 12 months as % of active population |
| `labour_force_participation_rate` | REAL | Yes | % | [0, 100] | Labour force participation rate (15-64) |
| `is_provisional` | INTEGER | No | boolean | {0, 1} | 1 = provisional/projected, 0 = confirmed |
| `source_key` | INTEGER | No (FK) | - | FK → dim_source | Data source reference |
| `created_at` | TEXT | No | timestamp | DEFAULT CURRENT_TIMESTAMP | Row creation timestamp |

**Unique constraint:** (`date_key`, `source_key`)

---

### Pillar 3: fact_credit

**Granularity:** Monthly (Jan 2010 to Dec 2025 = 192 rows)
**Primary Source:** Banco de Portugal BPStat (series 12457932, 12559924, 12457924, 12504544)

| Column | Data Type | Nullable | Unit | Constraints | Description |
|--------|-----------|----------|------|-------------|-------------|
| `id` | INTEGER | No (PK) | - | AUTOINCREMENT | Surrogate key |
| `date_key` | TEXT | No (FK) | - | FK → dim_date | Month key (e.g., `'2023-06'`) |
| `total_credit` | REAL | No | EUR millions | >= 0 | Total credit to non-financial sectors (BPStat 12457932). Includes NFC, households, and other non-financial entities — broader than NFC + households alone. |
| `credit_nfc` | REAL | Yes | EUR millions | >= 0 | Credit to non-financial corporations |
| `credit_households` | REAL | Yes | EUR millions | >= 0 | Credit to households |
| `npl_ratio` | REAL | Yes | % | [0, 100] | Non-performing loan ratio |
| `is_provisional` | INTEGER | No | boolean | {0, 1} | 1 = provisional/projected, 0 = confirmed |
| `source_key` | INTEGER | No (FK) | - | FK → dim_source | Data source reference |
| `created_at` | TEXT | No | timestamp | DEFAULT CURRENT_TIMESTAMP | Row creation timestamp |

**Unique constraint:** (`date_key`, `source_key`)
**Note:** Raw BPStat data has 180 rows (through 2024-12). The transform pipeline interpolates 12 additional months (Jan-Dec 2025).

---

### Pillar 4: fact_interest_rates

**Granularity:** Monthly (Jan 2010 to Dec 2025 = 192 rows)
**Primary Sources:** ECB Data API (`FM`, `IRS` flows)

| Column | Data Type | Nullable | Unit | Constraints | Description |
|--------|-----------|----------|------|-------------|-------------|
| `id` | INTEGER | No (PK) | - | AUTOINCREMENT | Surrogate key |
| `date_key` | TEXT | No (FK) | - | FK → dim_date | Month key (e.g., `'2023-06'`) |
| `ecb_main_refinancing_rate` | REAL | Yes | % | [-2, 20] | ECB main refinancing operations rate |
| `euribor_3m` | REAL | Yes | % | [-2, 20] | 3-month Euribor rate (monthly average) |
| `euribor_6m` | REAL | Yes | % | [-2, 20] | 6-month Euribor rate (monthly average) |
| `euribor_12m` | REAL | Yes | % | [-2, 20] | 12-month Euribor rate (monthly average) |
| `portugal_10y_bond_yield` | REAL | Yes | % | [-2, 30] | Portuguese 10-year government bond yield |
| `is_provisional` | INTEGER | No | boolean | {0, 1} | 1 = provisional/projected, 0 = confirmed |
| `source_key` | INTEGER | No (FK) | - | FK → dim_source | Data source reference |
| `created_at` | TEXT | No | timestamp | DEFAULT CURRENT_TIMESTAMP | Row creation timestamp |

**Unique constraint:** (`date_key`, `source_key`)
**Note:** ECB rate for Jan 2010-Mar 2011 is filled with known value 1.00% (API gap). ECB rate is forward-filled from daily to monthly.

---

### Pillar 5: fact_inflation

**Granularity:** Monthly (Jan 2010 to Dec 2025 = 192 rows)
**Primary Sources:** Eurostat SDMX (`prc_hicp_manr`, `prc_hicp_midx`)

| Column | Data Type | Nullable | Unit | Constraints | Description |
|--------|-----------|----------|------|-------------|-------------|
| `id` | INTEGER | No (PK) | - | AUTOINCREMENT | Surrogate key |
| `date_key` | TEXT | No (FK) | - | FK → dim_date | Month key (e.g., `'2023-06'`) |
| `hicp` | REAL | No | % | [-10, 30] | HICP annual rate of change (YoY) |
| `cpi_estimated` | REAL | Yes | % | [-10, 30] | **Estimated** CPI annual rate — derived from HICP with a small offset (mean -0.15 pp). Not sourced from INE. |
| `core_inflation` | REAL | Yes | % | [-10, 30] | Core inflation (excluding energy and food) YoY |
| `is_provisional` | INTEGER | No | boolean | {0, 1} | 1 = provisional/projected, 0 = confirmed |
| `source_key` | INTEGER | No (FK) | - | FK → dim_source | Data source reference |
| `created_at` | TEXT | No | timestamp | DEFAULT CURRENT_TIMESTAMP | Row creation timestamp |

**Unique constraint:** (`date_key`, `source_key`)
**Data quality note:** `cpi_estimated` is NOT real INE CPI data. See `docs/data_quality_report.md` section 3.2.

---

### Pillar 6: fact_public_debt

**Granularity:** Quarterly (2010-Q1 to 2025-Q4 = 64 rows)
**Primary Sources:** Eurostat SDMX (`gov_10q_ggdebt`, `gov_10q_ggnfa`, `gov_10dd_ggd`)

| Column | Data Type | Nullable | Unit | Constraints | Description |
|--------|-----------|----------|------|-------------|-------------|
| `id` | INTEGER | No (PK) | - | AUTOINCREMENT | Surrogate key |
| `date_key` | TEXT | No (FK) | - | FK → dim_date | Quarter key (e.g., `'2023-Q2'`) |
| `total_debt` | REAL | No | EUR millions | >= 0 | General government consolidated gross debt |
| `debt_to_gdp_ratio` | REAL | Yes | % | [0, 300] | Debt-to-GDP ratio (Eurostat methodology) |
| `budget_deficit` | REAL | Yes | % GDP | [-30, 10] | Quarterly budget balance as % of GDP (negative = deficit). Non-annualised. |
| `budget_deficit_annual` | REAL | Yes | % GDP | [-50, 10] | Annualised budget deficit (rolling average of last 4 quarters). More suitable for analysis. |
| `external_debt_share_estimated` | REAL | Yes | % | [0, 100] | Share of debt held by non-residents. Sourced from Eurostat `gov_10dd_ggd` where available (60/63 quarters); remaining quarters forward-filled. |
| `is_provisional` | INTEGER | No | boolean | {0, 1} | 1 = provisional/projected, 0 = confirmed |
| `source_key` | INTEGER | No (FK) | - | FK → dim_source | Data source reference |
| `created_at` | TEXT | No | timestamp | DEFAULT CURRENT_TIMESTAMP | Row creation timestamp |

**Unique constraint:** (`date_key`, `source_key`)
**Data quality notes:**
- `budget_deficit` contains non-annualised quarterly values with large seasonal swings (-19% to +7%). Use `budget_deficit_annual` for meaningful analysis.
- Raw Eurostat data has 63 rows (through 2025-Q3). The transform pipeline extrapolates 1 quarter (2025-Q4) via forward-fill.

---

## Source References

| Source Name | URL | Data Used |
|-------------|-----|-----------|
| INE | https://www.ine.pt | GDP, Unemployment, Inflation (CPI) — accessed indirectly via Eurostat |
| Banco de Portugal | https://bpstat.bportugal.pt | Credit (4 BPStat series) |
| PORDATA | https://www.pordata.pt | Cross-reference data |
| Eurostat | https://ec.europa.eu/eurostat | GDP, Unemployment, Inflation (HICP), Public Debt |
| ECB | https://www.ecb.europa.eu/stats | Interest Rates (ECB rates, Euribor, PT 10Y bond yield) |

---

## Data Quality Rules

| Rule | Scope | Description |
|------|-------|-------------|
| Not null | All primary metrics | Core indicators must not contain null values |
| Range check | Rates and percentages | Values must be within bounds defined in CHECK constraints above |
| Temporal completeness | All fact tables | No gaps in the time series within the defined period |
| Referential integrity | All foreign keys | Every `date_key` and `source_key` must exist in the respective dimension table |
| Type enforcement | All columns | Strict data type validation during ETL load stage |
| Provisional flagging | All fact tables | Data beyond publication lag window is flagged `is_provisional = 1` |

---

## Data Quality Notes

The following data quality issues have been identified and documented for transparency.
Users of this data should be aware of these limitations when performing analyses.

### Estimated / Synthetic Data

| Column | Table | Issue | Details |
|--------|-------|-------|---------|
| `cpi_estimated` | fact_inflation | **100% synthetic** | Eurostat returns identical HICP and CPI values. The ETL applies a random offset `N(-0.15, 0.08)` with seed 42 to simulate the typical INE CPI deviation. The `cpi_is_estimated` flag column indicates when this offset was applied. **Do not use for official CPI analysis.** |
| `external_debt_share_estimated` | fact_public_debt | **Forward-filled for 2025** | Eurostat `gov_10dd_ggd` data is not yet available for 2025. Values are forward-filled from Q4 2024 (44.67%). If API data is completely missing, a synthetic linear estimate (~48%→46%) is generated. |
| EU benchmark data | raw_eu_benchmark.csv | **Explicitly synthetic** | All benchmark data is marked as "Eurostat/ECB (synthetic benchmark)". Do not use for official cross-country comparisons. |

### Interpolated Data

| Column | Table | Issue | Details |
|--------|-------|-------|---------|
| Credit (all columns) | fact_credit | **~15 months interpolated** | BdP credit data transitions from quarterly to monthly around mid-2011. Months Apr-Jun 2010, Jul-Dec 2010, Jan-Jun 2011 are linearly interpolated from quarterly observations. |
| `npl_ratio` | fact_credit | **Quarterly frequency** | NPL ratio is reported quarterly by BdP but stored monthly. Intra-quarter months carry the same value (step function, not interpolated). |
| `long_term_unemployment_rate` | fact_unemployment | **Quarterly source** | Eurostat `une_ltu_q` is quarterly. Monthly values within each quarter are linearly interpolated. |

### Annual Data Spread to Sub-Annual

| Column | Table | Issue | Details |
|--------|-------|-------|---------|
| `gdp_per_capita` | fact_gdp | **Annual value** | GDP per capita from Eurostat `nama_10_pc` is annual. All 4 quarters of the same year carry the same value. |
| `external_debt_share_estimated` | fact_public_debt | **Annual source** | Eurostat `gov_10dd_ggd` is annual; values are interpolated to quarterly frequency. |

### Provisional / Projected Data

| Period | Issue | Details |
|--------|-------|---------|
| H2 2025 (Jul-Dec) | **Likely projections** | Data for the second half of 2025 may be synthetic or projected rather than confirmed Eurostat/ECB releases. Evidence: ECB main refinancing rate is missing for Jul-Dec 2025; public debt Q4 2025 does not exist in raw data and is extrapolated. Rows are flagged with `is_provisional = 1`. |

### Budget Balance Seasonality

Quarterly `budget_deficit` values can show extreme volatility due to fiscal seasonality (e.g., Q4 2010 = -19.1%, Q3 2023 = +7.3%). These are **not errors** — they reflect concentration of tax revenue or expenditure in specific quarters. The `budget_deficit_annual` column (rolling 4-quarter average) should be preferred for trend analysis.

### GDP Growth Rates

The raw file (`raw_gdp.csv`) contains **nominal** GDP growth rates (`nominal_gdp_growth_rate_yoy`, `nominal_gdp_growth_rate_qoq`). During transformation, these are **recalculated from real GDP** (`real_gdp_eur_millions`) to produce real growth rates in the processed output. The nominal rates in the raw file should not be confused with real growth.

### Benchmark vs Quarterly Data Discrepancies

The EU benchmark file uses annual averages which may differ from Q4 end-of-year readings in the quarterly data. Example: debt-to-GDP 2023 benchmark = 98.49% vs Q4 2023 quarterly = 96.9% (difference of 1.6 pp). This is expected when comparing annual averages with point-in-time quarterly readings.
