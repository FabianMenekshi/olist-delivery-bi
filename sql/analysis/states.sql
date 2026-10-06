SELECT
    customer_state,
    COUNT(*) AS all_orders,
    COUNT(*) FILTER(
        WHERE eligible_delivery
    ) AS eligible_orders,
    COUNT(*) FILTER(
        WHERE is_late
    ) AS late_orders,
    AVG(is_late::INT)::FLOAT AS late_rate,
    PERCENTILE_CONT(0.9) WITHIN GROUP(
        ORDER BY delivery_days
    )::FLOAT AS p90_delivery_days,
    COUNT(review_score) AS reviewed_orders,
    AVG(is_low_review::INT)::FLOAT AS low_review_rate
FROM olist_bi.order_mart
GROUP BY customer_state
ORDER BY late_orders DESC, customer_state;