SELECT
    COUNT(*) AS all_orders,
    COUNT(*) FILTER(
        WHERE order_status = 'delivered'
    ) AS delivered_orders,
    COUNT(*) FILTER(
        WHERE eligible_delivery
    ) AS eligible_orders,
    COUNT(*) FILTER(
        WHERE is_late
    ) AS late_orders,
    AVG(is_late::INT)::FLOAT AS late_rate,
    AVG(delivery_days)::FLOAT AS mean_delivery_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP(
        ORDER BY delivery_days
    )::FLOAT AS median_delivery_days,
    PERCENTILE_CONT(0.9) WITHIN GROUP(
        ORDER BY delivery_days
    )::FLOAT AS p90_delivery_days,
    COUNT(review_score) AS reviewed_orders,
    AVG(is_low_review::INT)::FLOAT AS low_review_rate,
    SUM(item_value)::FLOAT AS item_value_brl,
    SUM(freight_value)::FLOAT AS freight_value_brl,
    SUM(payment_value)::FLOAT AS payment_value_brl
FROM olist_bi.order_mart;