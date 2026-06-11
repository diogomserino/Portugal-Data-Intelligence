-- =============================================================================
-- Portugal Data Intelligence - Regional (NUTS2) Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_regional joined with dim_date
-- Period   : 2010 to 2025 (annual per NUTS2 region, YYYY-Q4 keys)
-- NUTS2    : PT11 Norte | PT15 Algarve | PT16 Centro | PT17 Lisboa
--            PT18 Alentejo | PT20 Acores | PT30 Madeira
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. LATEST GDP PER CAPITA BY REGION
--    Ranked from highest to lowest.
-- -----------------------------------------------------------------------------
SELECT
    r.nuts2_code,
    r.nuts2_name,
    ROUND(r.gdp_per_capita_pps, 0)         AS gdp_per_capita_pps,
    ROUND(r.gdp_index_eu27, 1)             AS gdp_index_eu27_100,
    ROUND(r.unemployment_rate, 1)          AS unemployment_rate_pct
FROM fact_regional r
JOIN dim_date d ON r.date_key = d.date_key
WHERE r.date_key = (SELECT MAX(date_key) FROM fact_regional)
ORDER BY r.gdp_per_capita_pps DESC;


-- -----------------------------------------------------------------------------
-- 2. REGIONAL CONVERGENCE OVER TIME
--    Coefficient of variation of GDP per capita — declining = convergence.
-- -----------------------------------------------------------------------------
WITH regional_cv AS (
    SELECT
        d.year,
        AVG(r.gdp_per_capita_pps)    AS mean_gdp,
        -- Population std dev approximation
        SQRT(
            AVG(r.gdp_per_capita_pps * r.gdp_per_capita_pps) -
            AVG(r.gdp_per_capita_pps) * AVG(r.gdp_per_capita_pps)
        )                            AS std_gdp,
        COUNT(*)                     AS n_regions
    FROM fact_regional r
    JOIN dim_date d ON r.date_key = d.date_key
    WHERE r.gdp_per_capita_pps IS NOT NULL
    GROUP BY d.year
)
SELECT
    year,
    ROUND(mean_gdp, 0)                     AS mean_gdp_pps,
    ROUND(std_gdp, 0)                      AS std_gdp_pps,
    ROUND(std_gdp / NULLIF(mean_gdp, 0), 4) AS coefficient_of_variation,
    n_regions
FROM regional_cv
ORDER BY year;


-- -----------------------------------------------------------------------------
-- 3. LISBOA vs REST OF PORTUGAL GDP GAP
--    Premium that Lisboa commands over the national average.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(
        MAX(CASE WHEN r.nuts2_code = 'PT17' THEN r.gdp_per_capita_pps END), 0
    )                                      AS lisboa_gdp_pps,
    ROUND(AVG(r.gdp_per_capita_pps), 0)   AS national_avg_gdp_pps,
    ROUND(
        MAX(CASE WHEN r.nuts2_code = 'PT17' THEN r.gdp_per_capita_pps END) /
        NULLIF(AVG(r.gdp_per_capita_pps), 0) - 1,
        3
    ) * 100                               AS lisboa_premium_pct
FROM fact_regional r
JOIN dim_date d ON r.date_key = d.date_key
WHERE r.gdp_per_capita_pps IS NOT NULL
GROUP BY d.year
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 4. UNEMPLOYMENT DISPERSION BY REGION
--    Best and worst region for unemployment each year.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    MIN(r.unemployment_rate)               AS min_unemp_rate,
    MAX(r.unemployment_rate)               AS max_unemp_rate,
    ROUND(
        MAX(r.unemployment_rate) - MIN(r.unemployment_rate), 1
    )                                      AS range_pp,
    MIN(CASE WHEN r.unemployment_rate = (
        SELECT MIN(r2.unemployment_rate) FROM fact_regional r2
        JOIN dim_date d2 ON r2.date_key = d2.date_key WHERE d2.year = d.year
    ) THEN r.nuts2_name END)               AS lowest_unemp_region,
    MIN(CASE WHEN r.unemployment_rate = (
        SELECT MAX(r2.unemployment_rate) FROM fact_regional r2
        JOIN dim_date d2 ON r2.date_key = d2.date_key WHERE d2.year = d.year
    ) THEN r.nuts2_name END)               AS highest_unemp_region
FROM fact_regional r
JOIN dim_date d ON r.date_key = d.date_key
WHERE r.unemployment_rate IS NOT NULL
GROUP BY d.year
ORDER BY d.year;
