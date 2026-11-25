-- =============================================================================
-- DBMS LAB END-SEM ASSIGNMENT (05 November 2026)
-- Student: S. Mohan Reddy | Roll No: 24MAB0A32
-- Deliverable 1: Exploratory Telemetry & Data Quality Queries (SQL)
-- Note: Written in standard SQL (DuckDB / PostgreSQL / SQLite compatible).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1(a) DAILY HEALTH BY DAY AND PLATFORM
-- Data quality handling:
--   1. Deduplicate purchase_id (122 duplicate webhook rows removed via GROUP BY).
--   2. Separate gross revenue (usd_amount > 0) from refunds/chargebacks (228 rows, -$3,274.72).
--   3. Format integer YYYYMMDD activity_date to ISO YYYY-MM-DD.
-- -----------------------------------------------------------------------------
WITH dedup_purchase AS (
    SELECT 
        purchase_id,
        device_id,
        MIN(event_ts) AS event_ts,
        pack_name,
        usd_amount,
        currency_granted,
        sale_flag
    FROM purchase
    GROUP BY purchase_id, device_id, pack_name, usd_amount, currency_granted, sale_flag
),
daily_active AS (
    SELECT 
        SUBSTR(CAST(pd.activity_date AS VARCHAR), 1, 4) || '-' || 
        SUBSTR(CAST(pd.activity_date AS VARCHAR), 5, 2) || '-' || 
        SUBSTR(CAST(pd.activity_date AS VARCHAR), 7, 2) AS dt,
        pp.platform,
        COUNT(DISTINCT pd.device_id) AS dau
    FROM player_day pd
    JOIN player_profile pp ON pd.device_id = pp.device_id
    GROUP BY 1, 2
),
daily_rev AS (
    SELECT 
        SUBSTR(p.event_ts, 1, 10) AS dt,
        pp.platform,
        SUM(CASE WHEN p.usd_amount > 0 THEN p.usd_amount ELSE 0 END) AS gross_revenue,
        SUM(p.usd_amount) AS net_revenue,
        COUNT(DISTINCT CASE WHEN p.usd_amount > 0 THEN p.device_id END) AS paying_dau
    FROM dedup_purchase p
    JOIN player_profile pp ON p.device_id = pp.device_id
    GROUP BY 1, 2
)
SELECT 
    da.dt,
    da.platform,
    da.dau,
    ROUND(COALESCE(dr.gross_revenue, 0), 2) AS gross_revenue,
    ROUND(COALESCE(dr.net_revenue, 0), 2) AS net_revenue,
    ROUND(COALESCE(dr.gross_revenue, 0) / NULLIF(da.dau, 0), 4) AS arpdau,
    ROUND(1.0 * COALESCE(dr.paying_dau, 0) / NULLIF(da.dau, 0), 4) AS payer_share
FROM daily_active da
LEFT JOIN daily_rev dr 
    ON da.dt = dr.dt AND da.platform = dr.platform
ORDER BY da.dt, da.platform;


-- -----------------------------------------------------------------------------
-- 1(b) WEEKLY INSTALL COHORT RETENTION TABLE (D1, D7, D14, D30)
-- Right-censoring rule:
--   Cohorts whose latest install_date + N days exceeds the telemetry cutoff
--   (2026-04-30) are set to NULL so incomplete observation windows do not
--   artificially depress retention rates. Pre-2026 installs are excluded since
--   their Day 0-30 activity occurred before telemetry logging began.
-- -----------------------------------------------------------------------------
WITH cohorts AS (
    SELECT 
        device_id,
        CAST(install_date AS DATE) AS install_date,
        DATE_TRUNC('week', CAST(install_date AS DATE))::DATE AS install_week
    FROM player_profile
    WHERE CAST(install_date AS DATE) >= DATE '2026-01-01'
),
activity_days AS (
    SELECT DISTINCT
        c.device_id,
        c.install_week,
        DATE_DIFF(
            'day',
            c.install_date,
            STRPTIME(CAST(pd.activity_date AS VARCHAR), '%Y%m%d')::DATE
        ) AS day_num
    FROM cohorts c
    JOIN player_day pd ON c.device_id = pd.device_id
)
SELECT 
    c.install_week,
    COUNT(DISTINCT c.device_id) AS cohort_size,
    CASE WHEN MAX(c.install_date) + INTERVAL '1 day' <= DATE '2026-04-30'
         THEN ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.day_num = 1 THEN a.device_id END) / COUNT(DISTINCT c.device_id), 2)
         ELSE NULL END AS d1_retention_pct,
    CASE WHEN MAX(c.install_date) + INTERVAL '7 days' <= DATE '2026-04-30'
         THEN ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.day_num = 7 THEN a.device_id END) / COUNT(DISTINCT c.device_id), 2)
         ELSE NULL END AS d7_retention_pct,
    CASE WHEN MAX(c.install_date) + INTERVAL '14 days' <= DATE '2026-04-30'
         THEN ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.day_num = 14 THEN a.device_id END) / COUNT(DISTINCT c.device_id), 2)
         ELSE NULL END AS d14_retention_pct,
    CASE WHEN MAX(c.install_date) + INTERVAL '30 days' <= DATE '2026-04-30'
         THEN ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.day_num = 30 THEN a.device_id END) / COUNT(DISTINCT c.device_id), 2)
         ELSE NULL END AS d30_retention_pct
FROM cohorts c
LEFT JOIN activity_days a 
    ON c.device_id = a.device_id AND a.day_num IN (1, 7, 14, 30)
GROUP BY c.install_week
ORDER BY c.install_week;


-- -----------------------------------------------------------------------------
-- 1(c-i) REVENUE CONCENTRATION (TOP 1%, 10%, 50% OF PAYING PLAYERS)
-- Population ranked: PAYERS ONLY (N = 11,054 deduplicated positive spenders).
-- (Ranking all 80,295 players yields Top 1% = 42.38%, Top 10% = 96.45%, Top 50% = 100.0%.)
-- -----------------------------------------------------------------------------
WITH dedup_purchase AS (
    SELECT purchase_id, device_id, MIN(event_ts) AS event_ts, usd_amount
    FROM purchase
    GROUP BY purchase_id, device_id, usd_amount
),
payer_rev AS (
    SELECT device_id, SUM(usd_amount) AS total_spend
    FROM dedup_purchase
    WHERE usd_amount > 0
    GROUP BY device_id
),
ranked AS (
    SELECT 
        device_id,
        total_spend,
        ROW_NUMBER() OVER (ORDER BY total_spend DESC) AS rn,
        COUNT(*) OVER () AS total_payers,
        SUM(total_spend) OVER () AS grand_total
    FROM payer_rev
)
SELECT 
    MAX(total_payers) AS total_payers,
    ROUND(MAX(grand_total), 2) AS total_gross_revenue,
    ROUND(100.0 * SUM(CASE WHEN rn <= 0.01 * total_payers THEN total_spend ELSE 0 END) / MAX(grand_total), 2) AS top_1pct_rev_share,
    ROUND(100.0 * SUM(CASE WHEN rn <= 0.10 * total_payers THEN total_spend ELSE 0 END) / MAX(grand_total), 2) AS top_10pct_rev_share,
    ROUND(100.0 * SUM(CASE WHEN rn <= 0.50 * total_payers THEN total_spend ELSE 0 END) / MAX(grand_total), 2) AS top_50pct_rev_share
FROM ranked;


-- -----------------------------------------------------------------------------
-- 1(c-ii) TIME TO FIRST PURCHASE & SHARE WHO NEVER PAY
-- -----------------------------------------------------------------------------
WITH dedup_purchase AS (
    SELECT purchase_id, device_id, MIN(event_ts) AS event_ts, usd_amount
    FROM purchase
    GROUP BY purchase_id, device_id, usd_amount
),
first_buy AS (
    SELECT 
        pp.device_id,
        CAST(pp.install_date AS DATE) AS install_date,
        MIN(DATE_TRUNC('day', CAST(p.event_ts AS TIMESTAMP))::DATE) AS first_buy_dt
    FROM player_profile pp
    LEFT JOIN dedup_purchase p 
        ON pp.device_id = p.device_id AND p.usd_amount > 0
    GROUP BY pp.device_id, pp.install_date
),
deltas AS (
    SELECT 
        device_id,
        DATE_DIFF('day', install_date, first_buy_dt) AS days_to_first_buy
    FROM first_buy
)
SELECT 
    COUNT(*) AS total_players,
    SUM(CASE WHEN days_to_first_buy IS NULL THEN 1 ELSE 0 END) AS never_paid_players,
    ROUND(100.0 * SUM(CASE WHEN days_to_first_buy IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS never_paid_pct,
    COUNT(days_to_first_buy) AS paying_players,
    ROUND(AVG(days_to_first_buy), 2) AS mean_days,
    PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY days_to_first_buy) AS p10_days,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_to_first_buy) AS p25_days,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_to_first_buy) AS median_days,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_to_first_buy) AS p75_days,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY days_to_first_buy) AS p90_days
FROM deltas;


-- -----------------------------------------------------------------------------
-- 1(c-iii) REPEAT PURCHASE GAP (USING WINDOW FUNCTION LAG)
-- -----------------------------------------------------------------------------
WITH dedup_purchase AS (
    SELECT purchase_id, device_id, MIN(event_ts) AS event_ts, usd_amount
    FROM purchase
    GROUP BY purchase_id, device_id, usd_amount
),
ordered_purchases AS (
    SELECT 
        device_id,
        CAST(event_ts AS TIMESTAMP) AS ts,
        LAG(CAST(event_ts AS TIMESTAMP)) OVER (
            PARTITION BY device_id ORDER BY CAST(event_ts AS TIMESTAMP)
        ) AS prev_ts
    FROM dedup_purchase
    WHERE usd_amount > 0
),
gaps AS (
    SELECT 
        device_id,
        EXTRACT(EPOCH FROM (ts - prev_ts)) / 86400.0 AS gap_days
    FROM ordered_purchases
    WHERE prev_ts IS NOT NULL
)
SELECT 
    COUNT(*) AS repeat_purchase_events,
    COUNT(DISTINCT device_id) AS repeat_payers,
    ROUND(AVG(gap_days), 2) AS mean_gap_days,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gap_days), 2) AS p25_gap_days,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gap_days), 2) AS median_gap_days,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY gap_days), 2) AS p75_gap_days
FROM gaps;


-- -----------------------------------------------------------------------------
-- 1(d) REWARDED AD ENGAGEMENT & CAP SATURATION
-- Data quality handling:
--   1. Filter status = 'completed' (started/abandoned rows do not grant rewards).
--   2. Filter event_ts <= '2026-04-30 23:59:59' (7,732 rows spill into May 1).
-- -----------------------------------------------------------------------------
WITH player_ad_days AS (
    SELECT 
        device_id,
        SUBSTR(event_ts, 1, 10) AS ad_date,
        MAX(ad_daily_cap) AS daily_cap,
        MAX(ad_daily_count) AS max_daily_count,
        COUNT(*) AS completed_ads
    FROM ad_view
    WHERE status = 'completed'
      AND SUBSTR(event_ts, 1, 10) <= '2026-04-30'
    GROUP BY 1, 2
)
SELECT 
    daily_cap,
    COUNT(*) AS ad_watching_player_days,
    SUM(CASE WHEN max_daily_count >= daily_cap THEN 1 ELSE 0 END) AS hit_cap_days,
    ROUND(100.0 * SUM(CASE WHEN max_daily_count >= daily_cap THEN 1 ELSE 0 END) / COUNT(*), 2) AS hit_cap_pct
FROM player_ad_days
GROUP BY daily_cap
ORDER BY daily_cap;

-- Daily ad view volume across the 120-day window (identifies Jan 1 partial day & Mar 5/7 drop)
SELECT 
    SUBSTR(event_ts, 1, 10) AS dt,
    COUNT(*) AS total_ad_events,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) AS completed_ads,
    COUNT(CASE WHEN status = 'started' THEN 1 END) AS started_ads,
    COUNT(CASE WHEN status = 'abandoned' THEN 1 END) AS abandoned_ads
FROM ad_view
WHERE SUBSTR(event_ts, 1, 10) <= '2026-04-30'
GROUP BY 1
ORDER BY 1;
