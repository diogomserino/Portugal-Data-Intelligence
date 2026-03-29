-- =============================================================================
-- Portugal Data Intelligence - DDL: EU Benchmark Tables
-- =============================================================================
-- Database : portugal_data_intelligence.db  (SQLite)
-- Purpose  : Store macroeconomic indicators for EU peer countries to enable
--            benchmarking of Portugal's performance against key European peers
--            and EU/Euro Area averages.
-- Period   : 2010-2025 (annual granularity)
-- Created  : March 2026
-- =============================================================================

-- -----------------------------------------------------------------------------
-- fact_eu_benchmark  -  Annual EU Benchmark Indicators
-- Granularity: annual (2010-2025, 16 rows per country per indicator).
-- Countries : PT, DE, ES, FR, IT, EU_AVG, EA_AVG
-- Indicators: gdp_growth, unemployment, inflation, debt_to_gdp, interest_rate_10y
-- Primary sources: Eurostat, ECB.
-- -----------------------------------------------------------------------------

DROP TABLE IF EXISTS fact_eu_benchmark;

CREATE TABLE fact_eu_benchmark (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key        TEXT    NOT NULL,                                       -- Year as 'YYYY'
    country_code    TEXT    NOT NULL
        CHECK(country_code IN ('PT', 'DE', 'ES', 'FR', 'IT', 'EU_AVG', 'EA_AVG')),
    country_name    TEXT    NOT NULL,                                       -- Full country/aggregate name
    indicator       TEXT    NOT NULL
        CHECK(indicator IN ('gdp_growth', 'unemployment', 'inflation', 'debt_to_gdp', 'interest_rate_10y')),
    value           REAL    NOT NULL,                                       -- Indicator value (units depend on indicator)
    source          TEXT,                                                     -- Data provenance (e.g. 'Eurostat/ECB')
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (date_key, country_code, indicator)
);

CREATE INDEX idx_eu_benchmark_date      ON fact_eu_benchmark (date_key);
CREATE INDEX idx_eu_benchmark_country   ON fact_eu_benchmark (country_code);
CREATE INDEX idx_eu_benchmark_indicator ON fact_eu_benchmark (indicator);
CREATE INDEX idx_eu_benchmark_composite ON fact_eu_benchmark (country_code, indicator, date_key);

-- =============================================================================
-- END OF DDL
-- =============================================================================
