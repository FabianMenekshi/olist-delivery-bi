-- Mutually exclusive order buckets: a multi-category order is counted once.
SELECT
    category,
    COUNT(*) AS all_orders,
    COUNT(*) FILTER(
        WHERE eligible_delivery
    ) AS eligible_orders,
    COUNT(*) FILTER(
        WHERE is_late
    ) AS late_orders,
    AVG(is_late::int)::FLOAT AS late_rate,
    COUNT(review_score) AS reviewed_orders,
    AVG(is_low_review::int)::FLOAT AS low_review_rate
FROM olist_bi.order_mart
GROUP BY category
ORDER BY late_orders DESC, category;