-- =============================================================================
-- Portugal Data Intelligence - External Accounts Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_external_accounts joined with dim_date
-- Period   : 2010-Q1 to 2025-Q4 (quarterly)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. CURRENT ACCOUNT BALANCE TREND
--    Quarterly current account and 4-quarter rolling average.
-- -----------------------------------------------------------------------------
SELECT
    e.date_key,
    d.year,
    d.quarter,
    ROUND(e.current_account_pct_gdp, 2)       AS current_account_pct_gdp,
    ROUND(e.trade_balance_pct_gdp, 2)         AS trade_balance_pct_gdp,
    ROUND(
        AVG(e.current_account_pct_gdp) OVER (
            ORDER BY e.date_key
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ), 2
    )                                         AS ca_rolling_4q_avg
FROM fact_external_accounts e
JOIN dim_date d ON e.date_key = d.date_key
WHERE e.current_account_pct_gdp IS NOT NULL
ORDER BY e.date_key;


-- -----------------------------------------------------------------------------
-- 2. ANNUAL EXTERNAL BALANCE SUMMARY
--    Average current account and REER per year.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(AVG(e.current_account_pct_gdp), 2)  AS avg_ca_pct_gdp,
    ROUND(AVG(e.trade_balance_pct_gdp), 2)    AS avg_trade_balance_pct_gdp,
    ROUND(AVG(e.reer_index), 1)               AS avg_reer_index,
    ROUND(AVG(e.export_growth_yoy), 2)        AS avg_export_growth_yoy_pct
FROM fact_external_accounts e
JOIN dim_date d ON e.date_key = d.date_key
GROUP BY d.year
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 3. REER APPRECIATION / DEPRECIATION
--    Year-on-year change in real effective exchange rate.
--    Positive = appreciation (competitiveness loss).
-- -----------------------------------------------------------------------------
WITH reer_annual AS (
    SELECT
        d.year,
        AVG(e.reer_index) AS avg_reer
    FROM fact_external_accounts e
    JOIN dim_date d ON e.date_key = d.date_key
    WHERE e.reer_index IS NOT NULL
    GROUP BY d.year
)
SELECT
    year,
    ROUND(avg_reer, 1)                                       AS reer_index,
    ROUND(
        (avg_reer / LAG(avg_reer) OVER (ORDER BY year) - 1) * 100,
        2
    )                                                        AS reer_change_yoy_pct
FROM reer_annual
ORDER BY year;
