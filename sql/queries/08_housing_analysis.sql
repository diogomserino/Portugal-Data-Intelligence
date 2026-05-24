-- =============================================================================
-- Portugal Data Intelligence - Housing Market Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_housing joined with dim_date
-- Period   : 2010 to 2025 (annual, YYYY-Q4 keys)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. HOUSE PRICE INDEX EVOLUTION
--    Year-on-year change and cumulative appreciation since 2010.
-- -----------------------------------------------------------------------------
WITH base AS (
    SELECT
        d.year,
        h.house_price_index,
        h.house_price_yoy_change,
        h.avg_price_per_sqm,
        h.housing_transactions
    FROM fact_housing h
    JOIN dim_date d ON h.date_key = d.date_key
    WHERE h.house_price_index IS NOT NULL
    ORDER BY d.year
),
base_2010 AS (
    SELECT house_price_index AS idx_2010 FROM base WHERE year = 2010
)
SELECT
    b.year,
    ROUND(b.house_price_index, 1)                        AS hpi,
    ROUND(b.house_price_yoy_change, 2)                   AS hpi_yoy_pct,
    ROUND(b.avg_price_per_sqm, 0)                        AS avg_eur_per_sqm,
    ROUND(b.housing_transactions, 0)                     AS transactions,
    ROUND((b.house_price_index / bx.idx_2010 - 1) * 100, 1) AS cumulative_change_since_2010_pct
FROM base b, base_2010 bx
ORDER BY b.year;


-- -----------------------------------------------------------------------------
-- 2. MORTGAGE LENDING TREND
--    New loan origination volume and year-on-year growth.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(h.mortgage_new_loans, 0)                       AS new_mortgage_loans_eur_m,
    ROUND(
        (h.mortgage_new_loans / LAG(h.mortgage_new_loans) OVER (ORDER BY d.year) - 1) * 100,
        1
    )                                                    AS mortgage_growth_yoy_pct
FROM fact_housing h
JOIN dim_date d ON h.date_key = d.date_key
WHERE h.mortgage_new_loans IS NOT NULL
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 3. AFFORDABILITY PROXY
--    Ratio of average price per sqm to (nominal GDP per capita / 12).
--    Higher ratio implies lower affordability.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(h.avg_price_per_sqm, 0)                        AS avg_price_per_sqm,
    ROUND(g.gdp_per_capita, 0)                           AS gdp_per_capita_eur,
    ROUND(h.avg_price_per_sqm / (g.gdp_per_capita / 12.0), 2) AS months_income_per_sqm
FROM fact_housing h
JOIN dim_date d ON h.date_key = d.date_key
LEFT JOIN fact_gdp g ON SUBSTR(h.date_key, 1, 4) || '-Q4' = g.date_key
WHERE h.avg_price_per_sqm IS NOT NULL
  AND g.gdp_per_capita IS NOT NULL
ORDER BY d.year;
