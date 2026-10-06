-- Only eligible orders; review denominator excludes missing reviews.
SELECT
    CASE
        WHEN is_late
            THEN 'Late'
        ELSE 'On time'
    END AS delivery_group,
    COUNT(*) AS eligible_orders,
    COUNT(review_score) AS reviewed_orders,
    COUNT(*) FILTER(
        WHERE is_low_review
    ) AS low_review_orders,
    AVG(is_low_review::int)::FLOAT AS low_review_rate,
    AVG(review_score)::FLOAT AS mean_review_score
FROM olist_bi.order_mart
WHERE eligible_delivery
GROUP BY is_late
ORDER BY is_late;