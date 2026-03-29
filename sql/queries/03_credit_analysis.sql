-- =============================================================================
-- Portugal Data Intelligence - Credit Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_credit joined with dim_date (and fact_gdp for ratio query)
-- Period   : January 2010 - December 2025
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. CREDIT EVOLUTION
--    Total credit trend with year-over-year growth rate.
-- -----------------------------------------------------------------------------
WITH credit_with_lag AS (
    SELECT
        d.year,
        d.month,
        d.date_key,
        c.total_credit,
        c.credit_nfc,
        c.credit_households,
        LAG(c.total_credit, 12) OVER (ORDER BY d.year, d.month)
                                                      AS total_credit_12m_ago
    FROM fact_credit c
    JOIN dim_date d ON c.date_key = d.date_key
)
SELECT
    year,
    month,
    date_key,
    ROUND(total_credit, 2)                            AS total_credit_eur_m,
    ROUND(credit_nfc, 2)                              AS credit_nfc_eur_m,
    ROUND(credit_households, 2)                       AS credit_households_eur_m,
    ROUND(
        (total_credit - total_credit_12m_ago)
        / NULLIF(total_credit_12m_ago, 0) * 100.0, 2
    )                                                 AS total_credit_yoy_growth_pct
FROM credit_with_lag
ORDER BY year, month;


-- -----------------------------------------------------------------------------
-- 2. PORTFOLIO COMPOSITION
--    NFC vs household credit share over time.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    ROUND(c.total_credit, 2)                          AS total_credit_eur_m,
    ROUND(c.credit_nfc, 2)                            AS credit_nfc_eur_m,
    ROUND(c.credit_households, 2)                     AS credit_households_eur_m,
    ROUND(
        c.credit_nfc / NULLIF(c.total_credit, 0) * 100.0, 2
    )                                                 AS nfc_share_pct,
    ROUND(
        c.credit_households / NULLIF(c.total_credit, 0) * 100.0, 2
    )                                                 AS household_share_pct,
    ROUND(
        (c.total_credit - c.credit_nfc - c.credit_households)
        / NULLIF(c.total_credit, 0) * 100.0, 2
    )                                                 AS other_share_pct
FROM fact_credit c
JOIN dim_date d ON c.date_key = d.date_key
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 3. NPL RATIO TREND
--    Non-performing loans evolution with risk classification.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    ROUND(c.npl_ratio, 2)                            AS npl_ratio_pct,
    ROUND(
        AVG(c.npl_ratio) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    )                                                 AS npl_ratio_12m_ma,
    CASE
        WHEN c.npl_ratio < 3   THEN 'Healthy'
        WHEN c.npl_ratio < 7   THEN 'Warning'
        ELSE                         'Critical'
    END                                               AS npl_classification,
    LAG(c.npl_ratio, 12) OVER (ORDER BY d.year, d.month)
                                                      AS npl_ratio_12m_ago,
    ROUND(
        c.npl_ratio - LAG(c.npl_ratio, 12) OVER (ORDER BY d.year, d.month), 2
    )                                                 AS npl_change_yoy_pp
FROM fact_credit c
JOIN dim_date d ON c.date_key = d.date_key
WHERE c.npl_ratio IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 4. CREDIT-TO-GDP RATIO
--    Join credit data with quarterly GDP to compute credit intensity.
--    Uses the quarter-end month credit value matched with quarterly GDP.
-- -----------------------------------------------------------------------------
WITH quarterly_credit AS (
    SELECT
        d.year,
        d.quarter,
        d.date_key,
        c.total_credit
    FROM fact_credit c
    JOIN dim_date d ON c.date_key = d.date_key
    WHERE d.is_quarter_end = 1
)
SELECT
    qc.year,
    qc.quarter,
    'Q' || qc.quarter                                AS quarter_label,
    ROUND(qc.total_credit, 2)                        AS total_credit_eur_m,
    ROUND(g.nominal_gdp, 2)                          AS nominal_gdp_eur_m,
    ROUND(
        qc.total_credit / NULLIF(g.nominal_gdp, 0) * 100.0, 2
    )                                                 AS credit_to_gdp_ratio_pct
FROM quarterly_credit qc
JOIN fact_gdp g ON qc.date_key = g.date_key
ORDER BY qc.year, qc.quarter;


-- -----------------------------------------------------------------------------
-- 5. DELEVERAGING ANALYSIS
--    Identify consecutive months of credit contraction.
--    Groups consecutive contraction months into episodes.
-- -----------------------------------------------------------------------------
WITH monthly_change AS (
    SELECT
        d.year,
        d.month,
        d.date_key,
        c.total_credit,
        LAG(c.total_credit, 1) OVER (ORDER BY d.year, d.month)
                                                      AS prev_month_credit,
        c.total_credit - LAG(c.total_credit, 1) OVER (ORDER BY d.year, d.month)
                                                      AS mom_change,
        CASE
            WHEN c.total_credit < LAG(c.total_credit, 1) OVER (ORDER BY d.year, d.month)
            THEN 1
            ELSE 0
        END                                           AS is_contraction
    FROM fact_credit c
    JOIN dim_date d ON c.date_key = d.date_key
),
-- Assign a group ID to each consecutive run of contraction months
contraction_groups AS (
    SELECT
        *,
        SUM(CASE WHEN is_contraction = 0 THEN 1 ELSE 0 END) OVER (
            ORDER BY year, month
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS contraction_group
    FROM monthly_change
    WHERE prev_month_credit IS NOT NULL
),
episodes AS (
    SELECT
        contraction_group,
        MIN(date_key)                                 AS episode_start,
        MAX(date_key)                                 AS episode_end,
        COUNT(*)                                      AS consecutive_months,
        ROUND(SUM(mom_change), 2)                     AS total_credit_change_eur_m,
        ROUND(
            SUM(mom_change) / NULLIF(MAX(total_credit), 0) * 100.0, 2
        )                                             AS pct_change_over_episode
    FROM contraction_groups
    WHERE is_contraction = 1
    GROUP BY contraction_group
    HAVING consecutive_months >= 3  -- Only significant episodes (3+ months)
)
SELECT
    episode_start,
    episode_end,
    consecutive_months,
    total_credit_change_eur_m,
    pct_change_over_episode
FROM episodes
ORDER BY consecutive_months DESC, episode_start;

-- =============================================================================
-- END OF CREDIT ANALYSIS
-- =============================================================================
