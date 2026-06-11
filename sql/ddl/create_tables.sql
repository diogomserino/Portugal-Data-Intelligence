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
DROP TABLE IF EXISTS fact_housing;
DROP TABLE IF EXISTS fact_labor_detail;
DROP TABLE IF EXISTS fact_external_accounts;
DROP TABLE IF EXISTS fact_fiscal;
DROP TABLE IF EXISTS fact_inequality;

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
    cpi_is_estimated INTEGER NOT NULL DEFAULT 0 CHECK(cpi_is_estimated IN (0, 1)), -- True if CPI was synthetically derived from HICP
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

-- -----------------------------------------------------------------------------
-- fact_housing  -  Annual House Price and Mortgage Statistics
-- Granularity: annual (2010-Q4 to 2025-Q4, 16 rows expected).
-- Primary sources: INE, Eurostat.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_housing (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key               TEXT    NOT NULL,                                        -- FK to dim_date (YYYY-Q4)
    house_price_index      REAL    CHECK(house_price_index > 0),                   -- HPI (2015=100)
    house_price_yoy_change REAL    CHECK(house_price_yoy_change BETWEEN -30 AND 80), -- HPI YoY change (%)
    housing_transactions   REAL    CHECK(housing_transactions >= 0),               -- Number of transactions
    avg_price_per_sqm      REAL    CHECK(avg_price_per_sqm > 0),                  -- Average price (EUR/m²)
    mortgage_new_loans     REAL    CHECK(mortgage_new_loans >= 0),                -- New mortgage loans (EUR millions)
    is_provisional         INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key             INTEGER NOT NULL,
    created_at             TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_housing_date_key ON fact_housing (date_key);

-- -----------------------------------------------------------------------------
-- fact_labor_detail  -  Annual Employment Structure and Wages
-- Granularity: annual (2010-Q4 to 2025-Q4, 16 rows expected).
-- Primary source: Eurostat.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_labor_detail (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key                    TEXT    NOT NULL,                                             -- FK to dim_date (YYYY-Q4)
    employment_services_pct     REAL    CHECK(employment_services_pct BETWEEN 0 AND 100),    -- % employed in services
    employment_industry_pct     REAL    CHECK(employment_industry_pct BETWEEN 0 AND 100),    -- % employed in industry
    employment_agriculture_pct  REAL    CHECK(employment_agriculture_pct BETWEEN 0 AND 100), -- % employed in agriculture
    real_wage_index             REAL    CHECK(real_wage_index > 0),                          -- Real wage index (2015=100)
    labour_productivity_index   REAL    CHECK(labour_productivity_index > 0),                -- Labour productivity index (2015=100)
    is_provisional              INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key                  INTEGER NOT NULL,
    created_at                  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_labor_detail_date_key ON fact_labor_detail (date_key);

-- -----------------------------------------------------------------------------
-- fact_external_accounts  -  Quarterly External Competitiveness
-- Granularity: quarterly (2010-Q1 to 2025-Q4, 64 rows expected).
-- Primary sources: ECB, Banco de Portugal, Eurostat.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_external_accounts (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key               TEXT    NOT NULL,                                             -- FK to dim_date (YYYY-QN)
    trade_balance_pct_gdp  REAL    CHECK(trade_balance_pct_gdp BETWEEN -30 AND 30),    -- Trade balance % GDP
    current_account_pct_gdp REAL   CHECK(current_account_pct_gdp BETWEEN -30 AND 30), -- Current account % GDP
    reer_index             REAL    CHECK(reer_index > 0),                               -- REER (2015=100)
    export_growth_yoy      REAL    CHECK(export_growth_yoy BETWEEN -50 AND 80),        -- Export growth YoY (%)
    is_provisional         INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key             INTEGER NOT NULL,
    created_at             TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_external_accounts_date_key ON fact_external_accounts (date_key);

-- -----------------------------------------------------------------------------
-- fact_fiscal  -  Annual Fiscal Composition (COFOG)
-- Granularity: annual (2010-Q4 to 2025-Q4, 16 rows expected).
-- Primary source: Eurostat (gov_10a_exp).
-- All values expressed as % of GDP.
-- -----------------------------------------------------------------------------

CREATE TABLE fact_fiscal (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key                    TEXT    NOT NULL,                                                   -- FK to dim_date (YYYY-Q4)
    total_revenue_pct_gdp       REAL    CHECK(total_revenue_pct_gdp BETWEEN 0 AND 80),             -- Total revenue % GDP
    total_expenditure_pct_gdp   REAL    CHECK(total_expenditure_pct_gdp BETWEEN 0 AND 80),         -- Total expenditure % GDP
    health_expenditure_pct      REAL    CHECK(health_expenditure_pct BETWEEN 0 AND 20),            -- Health % GDP
    education_expenditure_pct   REAL    CHECK(education_expenditure_pct BETWEEN 0 AND 15),         -- Education % GDP
    social_protection_pct       REAL    CHECK(social_protection_pct BETWEEN 0 AND 40),             -- Social protection % GDP
    interest_payments_pct       REAL    CHECK(interest_payments_pct BETWEEN 0 AND 15),             -- Interest payments % GDP
    is_provisional              INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key                  INTEGER NOT NULL,
    created_at                  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_fiscal_date_key ON fact_fiscal (date_key);

-- -----------------------------------------------------------------------------
-- fact_inequality  -  Annual Inequality and Income Indicators
-- Granularity: annual (2010-Q4 to 2025-Q4, 16 rows expected).
-- Primary source: Eurostat (EU-SILC).
-- -----------------------------------------------------------------------------

CREATE TABLE fact_inequality (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key             TEXT    NOT NULL,                                               -- FK to dim_date (YYYY-Q4)
    gini_index           REAL    CHECK(gini_index BETWEEN 0 AND 100),                  -- Gini coefficient (0-100)
    s80_s20_ratio        REAL    CHECK(s80_s20_ratio > 0),                             -- Income quintile share ratio
    poverty_risk_rate    REAL    CHECK(poverty_risk_rate BETWEEN 0 AND 100),           -- At-risk-of-poverty rate (%)
    median_income_index  REAL    CHECK(median_income_index > 0),                       -- Median equivalised income index (EU27=100)
    is_provisional       INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key           INTEGER NOT NULL,
    created_at           TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, source_key)
);

CREATE INDEX idx_fact_inequality_date_key ON fact_inequality (date_key);

-- -----------------------------------------------------------------------------
-- fact_regional  -  NUTS2 Regional Macroeconomic Indicators
-- Granularity: annual (YYYY-Q4), one row per NUTS2 region per year.
-- Primary source: Eurostat (nama_10r_2gdp, lfst_r_lfu3rt).
-- NUTS2 regions: PT11 Norte, PT15 Algarve, PT16 Centro, PT17 Lisboa,
--                PT18 Alentejo, PT20 Açores, PT30 Madeira.
-- -----------------------------------------------------------------------------

DROP TABLE IF EXISTS fact_regional;

CREATE TABLE fact_regional (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key                TEXT    NOT NULL,                                           -- FK to dim_date (YYYY-Q4)
    nuts2_code              TEXT    NOT NULL CHECK(LENGTH(nuts2_code) = 4),            -- e.g. 'PT17'
    nuts2_name              TEXT    NOT NULL,                                           -- e.g. 'Lisboa'
    gdp_per_capita_pps      REAL    CHECK(gdp_per_capita_pps > 0),                    -- GDP per capita in PPS (EUR)
    gdp_index_eu27          REAL    CHECK(gdp_index_eu27 > 0),                        -- GDP per capita as % of EU27=100
    unemployment_rate       REAL    CHECK(unemployment_rate BETWEEN 0 AND 50),        -- Regional unemployment rate (%)
    youth_unemployment_rate REAL    CHECK(youth_unemployment_rate BETWEEN 0 AND 80),  -- Youth unemployment rate (%)
    is_provisional          INTEGER NOT NULL DEFAULT 0 CHECK(is_provisional IN (0, 1)),
    source_key              INTEGER NOT NULL,
    created_at              TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (date_key)   REFERENCES dim_date   (date_key),
    FOREIGN KEY (source_key) REFERENCES dim_source (source_key),
    UNIQUE (date_key, nuts2_code, source_key)
);

CREATE INDEX idx_fact_regional_date_key  ON fact_regional (date_key);
CREATE INDEX idx_fact_regional_nuts2     ON fact_regional (nuts2_code);

-- =============================================================================
-- END OF DDL
-- =============================================================================
