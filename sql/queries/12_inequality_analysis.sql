-- =============================================================================
-- Portugal Data Intelligence - Inequality & Income Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_inequality joined with dim_date
-- Period   : 2010 to 2025 (annual, YYYY-Q4 keys)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. GINI INDEX AND INCOME RATIO TREND
--    Core inequality measures over time.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(i.gini_index, 1)               AS gini_index,
    ROUND(i.s80_s20_ratio, 2)            AS s80_s20_ratio,
    ROUND(i.poverty_risk_rate, 1)        AS poverty_risk_rate_pct,
    ROUND(i.median_income_index, 1)      AS median_income_eu27_idx
FROM fact_inequality i
JOIN dim_date d ON i.date_key = d.date_key
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 2. GINI TRAJECTORY — IMPROVING OR WORSENING?
--    Year-on-year change in Gini and poverty rate.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(i.gini_index, 1)                                AS gini,
    ROUND(
        i.gini_index -
        LAG(i.gini_index) OVER (ORDER BY d.year),
        2
    )                                                     AS gini_change_yoy,
    ROUND(i.poverty_risk_rate, 1)                         AS poverty_rate_pct,
    ROUND(
        i.poverty_risk_rate -
        LAG(i.poverty_risk_rate) OVER (ORDER BY d.year),
        2
    )                                                     AS poverty_change_yoy_pp
FROM fact_inequality i
JOIN dim_date d ON i.date_key = d.date_key
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 3. INEQUALITY VS UNEMPLOYMENT CORRELATION
--    Does higher unemployment coincide with higher inequality?
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(i.gini_index, 1)               AS gini_index,
    ROUND(i.poverty_risk_rate, 1)        AS poverty_risk_pct,
    ROUND(
        AVG(u.unemployment_rate), 1
    )                                    AS avg_unemployment_rate
FROM fact_inequality i
JOIN dim_date d ON i.date_key = d.date_key
LEFT JOIN fact_unemployment u ON SUBSTR(u.date_key, 1, 4) = CAST(d.year AS TEXT)
GROUP BY d.year, i.gini_index, i.poverty_risk_rate
ORDER BY d.year;
