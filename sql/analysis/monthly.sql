-- Purchase cohorts, NOT the month in which delivery happened.
-- Calendar spine makes a previous-month comparison truly consecutive.
WITH bounds AS (
    SELECT
        MIN(purchase_month) lo,
        MAX(purchase_month) hi
    FROM olist_bi.order_mart
),
calendar AS (
    SELECT
        GENERATE_SERIES(lo,hi,interval '1 month')::DATE AS month
    FROM bounds
),
grouped AS (
    SELECT
        purchase_month AS month,
        COUNT(*) AS all_orders,
        COUNT(*) FILTER(
            WHERE eligible_delivery
        ) AS eligible_orders,
        COUNT(*) FILTER(
            WHERE is_late
        ) AS late_orders,
        AVG(is_late::int)::float AS late_rate,
        PERCENTILE_CONT(0.9) WITHIN GROUP(
            ORDER BY delivery_days
        )::float AS p90_delivery_days
    FROM olist_bi.order_mart
    WHERE purchase_month IS NOT NULL
    GROUP BY purchase_month
),
filled AS (
    SELECT
        c.month,
        COALESCE(g.all_orders,0) all_orders,
        COALESCE(g.eligible_orders,0) eligible_orders,
        COALESCE(g.late_orders,0) late_orders,
        g.late_rate,
        g.p90_delivery_days
    FROM calendar c
    LEFT JOIN grouped g
        USING(month)
)
SELECT
    *,
    100 * (
        late_rate - LAG(late_rate) OVER(
            ORDER BY month
        )
    ) AS late_rate_change_pp
FROM filled
ORDER BY month;