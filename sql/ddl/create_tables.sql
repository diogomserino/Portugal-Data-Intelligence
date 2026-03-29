-- =============================================================================
-- Portugal Data Intelligence - DDL: Create Tables
-- =============================================================================
-- Database : portugal_data_intelligence.db  (SQLite)
-- Schema   : Star schema with 2 dimension tables and 6 fact tables
-- Period   : January 2010 - December 2025
-- Created  : March 2026
--
-- IMPORTANT: Mixed date_key granularity
-- ──────────────────────────────────────
-- Monthly pillars (unemployment, credit, interest_rates, inflation)
--   use date_key format 'YYYY-MM'  (e.g. '2023-06').
-- Quarterly pillars (gdp, public_debt)
--   use date_key format 'YYYY-QN'  (e.g. '2023-Q2').
--
-- When joining quarterly and monthly tables, convert quarterly keys to
-- the quarter-end month:
--   CASE SUBSTR(q.date_key, 6, 1)
--     WHEN '1' THEN SUBSTR(q.date_key, 1, 4) || '-03'
--     WHEN '2' THEN SUBSTR(q.date_key, 1, 4) || '-06'
--     WHEN '3' THEN SUBSTR(q.date_key, 1, 4) || '-09'
--     WHEN '4' THEN SUBSTR(q.date_key, 1, 4) || '-12'
--   END
-- Or aggregate monthly data to quarters using SUBSTR(m.date_key, 1, 4)
-- and the quarter mapping before joining.
-- =============================================================================

-- Temporarily disable FK checks so we can DROP tables in any order.
PRAGMA foreign_keys = OFF;

-- Drop fact tables first (they reference dimension tables)
DROP TABLE IF EXISTS fact_gdp;
DROP TABLE IF EXISTS fact_unemployment;
DROP TABLE IF EXISTS fact_credit;
DROP TABLE IF EXISTS fact_interest_rates;
DROP TABLE IF EXISTS fact_inflation;
DROP TABLE IF EXISTS fact_public_debt;

-- =============================================================================
-- DIMENSION TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dim_date  -  Calendar dimension
-- One row per month from 2010-01 to 2025-12 (192 rows).
-- date_key uses YYYY-MM format for monthly data and YYYY-QN for quarterly
-- lookups.  Fact tables join on the YYYY-MM key corresponding to the
-- quarter-end month for quarterly series.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key        TEXT    NOT NULL PRIMARY KEY,   -- 'YYYY-MM' or 'YYYY-QN'
    full_date       TEXT    NOT NULL,               -- ISO date 'YYYY-MM-DD' (first day of month)
    year            INTEGER NOT NULL CHECK(year BETWEEN 2010 AND 2030),
    quarter         INTEGER NOT NULL CHECK(quarter BETWEEN 1 AND 4),
    month           INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    month_name      TEXT    NOT NULL,               -- Full month name (e.g. 'January')
    is_quarter_end  INTEGER NOT NULL DEFAULT 0 CHECK(is_quarter_end IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- dim_source  -  Data source reference
-- One row per institutional data provider (INE, Banco de Portugal, etc.).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_source;

CREATE TABLE dim_source (
    source_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT    NOT NULL UNIQUE,            -- e.g. 'INE', 'Banco de Portugal'
    source_url  TEXT,                               -- Official website URL
    description TEXT                                -- Brief description
);

-- =============================================================================
-- FACT TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- fact_gdp  -  Quarterly Gross Domestic Product
-- Granularity: quarterly (2010-Q1 to 2025-Q4, 64 rows expected).
-- Primary sources: INE, Eurostat.
-- Monetary values in EUR millions.
-- -----------------------------------------------------------------------------

-- Re-enable FK checks before creating tables with constraints
PRAGMA foreign_keys = ON;

CREATE TABLE fact_gdp (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key        TEXT    NOT NULL,               -- FK to dim_date (YYYY-MM of quarter-end)
    nominal_gdp     REAL    NOT NULL,               -- Nominal GDP in EUR millions
    real_gdp        REAL,                           -- Real GDP in EUR millions (base year 2015)
    gdp_growth_yoy  REAL    CHECK(gdp_growth_yoy BETWEEN -50 AND 50),  -- YoY growth rate (%) — derived from real_gdp
    gdp_growth_qoq  REAL    CHECK(gdp_growth_qoq BETWEEN -30 AND 30),  -- QoQ growth rate (%) — derived from real_gdp
    gdp_per_capita  REAL    CHECK(gdp_per_capita >= 0),                 -- GDP per capita (EUR)
    is_provisional  INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),  -- 1 = projected/preliminary
    source_key      INTEGER NOT NULL,               -- FK to dim_source
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_gdp_date_key   ON fact_gdp (date_key);
CREATE INDEX idx_fact_gdp_source_key ON fact_gdp (source_key);

-- -----------------------------------------------------------------------------
-- fact_unemployment  -  Monthly Unemployment Statistics
-- Granularity: monthly (Jan 2010 - Dec 2025, 192 rows expected).
-- Primary sources: INE, Eurostat.
-- All rates expressed as percentages.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_unemployment (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key                        TEXT    NOT NULL,                                     -- FK to dim_date (YYYY-MM)
    unemployment_rate               REAL    NOT NULL CHECK(unemployment_rate BETWEEN 0 AND 50),
    youth_unemployment_rate         REAL    CHECK(youth_unemployment_rate BETWEEN 0 AND 80),
    long_term_unemployment_rate     REAL    CHECK(long_term_unemployment_rate BETWEEN 0 AND 50),
    labour_force_participation_rate REAL    CHECK(labour_force_participation_rate BETWEEN 0 AND 100),
    is_provisional                  INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key                      INTEGER NOT NULL,                                    -- FK to dim_source
    created_at                      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_unemployment_date_key   ON fact_unemployment (date_key);
CREATE INDEX idx_fact_unemployment_source_key ON fact_unemployment (source_key);

-- -----------------------------------------------------------------------------
-- fact_credit  -  Monthly Credit to the Economy
-- Granularity: monthly (Jan 2010 - Dec 2025, 192 rows expected).
-- Primary source: Banco de Portugal.
-- Monetary values in EUR millions; NPL ratio in percentage.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_credit (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key          TEXT    NOT NULL,                              -- FK to dim_date (YYYY-MM)
    total_credit      REAL    NOT NULL CHECK(total_credit >= 0),     -- Total credit outstanding (EUR millions)
    credit_nfc        REAL    CHECK(credit_nfc >= 0),               -- Credit to non-financial corporations (EUR millions)
    credit_households REAL    CHECK(credit_households >= 0),        -- Credit to households (EUR millions)
    npl_ratio         REAL    CHECK(npl_ratio BETWEEN 0 AND 100),   -- Non-performing loan ratio (%)
    is_provisional    INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key        INTEGER NOT NULL,                              -- FK to dim_source
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_credit_date_key   ON fact_credit (date_key);
CREATE INDEX idx_fact_credit_source_key ON fact_credit (source_key);

-- -----------------------------------------------------------------------------
-- fact_interest_rates  -  Monthly Interest Rates
-- Granularity: monthly (Jan 2010 - Dec 2025, 192 rows expected).
-- Primary sources: Banco de Portugal, ECB.
-- All rates expressed as percentages. Negative rates are valid (ECB era).
-- -----------------------------------------------------------------------------

CREATE TABLE fact_interest_rates (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key                    TEXT    NOT NULL,                                         -- FK to dim_date (YYYY-MM)
    ecb_main_refinancing_rate   REAL    CHECK(ecb_main_refinancing_rate BETWEEN -2 AND 20),
    euribor_3m                  REAL    CHECK(euribor_3m BETWEEN -2 AND 20),
    euribor_6m                  REAL    CHECK(euribor_6m BETWEEN -2 AND 20),
    euribor_12m                 REAL    CHECK(euribor_12m BETWEEN -2 AND 20),
    portugal_10y_bond_yield     REAL    CHECK(portugal_10y_bond_yield BETWEEN -2 AND 30), -- Troika peak ~17%
    is_provisional              INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key                  INTEGER NOT NULL,                                         -- FK to dim_source
    created_at                  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_interest_rates_date_key   ON fact_interest_rates (date_key);
CREATE INDEX idx_fact_interest_rates_source_key ON fact_interest_rates (source_key);

-- -----------------------------------------------------------------------------
-- fact_inflation  -  Monthly Inflation Indicators
-- Granularity: monthly (Jan 2010 - Dec 2025, 192 rows expected).
-- Primary sources: INE, Eurostat.
-- All rates expressed as year-on-year percentages. Negative = deflation.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_inflation (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key        TEXT    NOT NULL,                                       -- FK to dim_date (YYYY-MM)
    hicp            REAL    NOT NULL CHECK(hicp BETWEEN -10 AND 30),        -- HICP YoY (%)
    cpi_estimated   REAL    CHECK(cpi_estimated BETWEEN -10 AND 30),       -- CPI YoY (%) — estimated from HICP, not INE source
    core_inflation  REAL    CHECK(core_inflation BETWEEN -10 AND 30),      -- Core inflation excl. energy/food (%)
    is_provisional  INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key      INTEGER NOT NULL,                                       -- FK to dim_source
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_inflation_date_key   ON fact_inflation (date_key);
CREATE INDEX idx_fact_inflation_source_key ON fact_inflation (source_key);

-- -----------------------------------------------------------------------------
-- fact_public_debt  -  Quarterly Public Debt
-- Granularity: quarterly (2010-Q1 to 2025-Q4, 64 rows expected).
-- Primary sources: Banco de Portugal, PORDATA.
-- Monetary values in EUR millions; ratios in percentages.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_public_debt (
    id                           INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key                     TEXT    NOT NULL,                                            -- FK to dim_date (YYYY-MM of quarter-end)
    total_debt                   REAL    NOT NULL CHECK(total_debt >= 0),                     -- General government gross debt (EUR millions)
    debt_to_gdp_ratio            REAL    CHECK(debt_to_gdp_ratio BETWEEN 0 AND 300),         -- Debt-to-GDP ratio (%)
    budget_deficit               REAL    CHECK(budget_deficit BETWEEN -30 AND 10),            -- Budget balance as % of GDP (negative = deficit, quarterly)
    budget_deficit_annual        REAL    CHECK(budget_deficit_annual BETWEEN -50 AND 10),     -- Annualised budget deficit (rolling 4-quarter average)
    external_debt_share_estimated REAL   CHECK(external_debt_share_estimated BETWEEN 0 AND 100), -- Estimated share of debt held by non-residents (%)
    is_provisional               INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key                   INTEGER NOT NULL,                                            -- FK to dim_source
    created_at                   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_public_debt_date_key   ON fact_public_debt (date_key);
CREATE INDEX idx_fact_public_debt_source_key ON fact_public_debt (source_key);

-- =============================================================================
-- END OF DDL
-- =============================================================================
