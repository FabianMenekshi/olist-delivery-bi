-- Every query produces an issue count. Errors stop a run; warnings are exported.
SELECT
    'order_count_reconciles' AS check_name,
    'error' AS severity,
    ABS((
        SELECT COUNT(*)
        FROM olist_raw.orders)-(
            SELECT COUNT(*)
            FROM olist_bi.order_mart
        )) AS issues
UNION ALL
SELECT
    'unique_order_grain','error',
    COUNT(*) - COUNT(DISTINCT order_id)
    FROM olist_bi.order_mart
UNION ALL
SELECT
    'item_value_reconciles','error',
    CASE
        WHEN COALESCE((
            SELECT SUM(price)
            FROM olist_raw.items),0) = COALESCE((
                SELECT SUM(item_value)
                FROM olist_bi.order_mart),0)
            THEN 0
        ELSE 1
    END
UNION ALL
SELECT
    'payments_reconcile','error',
    CASE
        WHEN COALESCE((
            SELECT SUM(payment_value)
            FROM olist_raw.payments),0) = COALESCE((
                SELECT SUM(payment_value)
                FROM olist_bi.order_mart),0)
            THEN 0
        ELSE 1
    END
UNION ALL
SELECT
    'freight_reconciles','error',
    CASE
        WHEN COALESCE((
            SELECT SUM(freight_value)
            FROM olist_raw.items),0) = COALESCE((
                SELECT SUM(freight_value)
                FROM olist_bi.order_mart),0)
            THEN 0
        ELSE 1
    END
UNION ALL
SELECT
    'no_orders','error',
    CASE
        WHEN COUNT(*) = 0
            THEN 1
        ELSE 0
    END
    FROM olist_raw.orders
UNION ALL
SELECT
    'missing_purchase_timestamp','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE order_purchase_timestamp IS NULL
UNION ALL
SELECT
    'delivered_but_ineligible','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE order_status = 'delivered'
        AND NOT eligible_delivery
UNION ALL
SELECT
    'delivery_before_purchase','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE order_delivered_customer_date < order_purchase_timestamp
UNION ALL
SELECT
    'carrier_before_purchase','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE order_delivered_carrier_date < order_purchase_timestamp
UNION ALL
SELECT
    'customer_before_carrier','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE order_delivered_customer_date < order_delivered_carrier_date
UNION ALL
SELECT
    'estimated_before_purchase_date','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE order_estimated_delivery_date::DATE < order_purchase_timestamp::DATE
UNION ALL
SELECT
    'multiple_reviews_orders','warning',
    COUNT(*)
    FROM (
        SELECT order_id
        FROM olist_raw.reviews
        GROUP BY order_id
        HAVING COUNT(*) > 1
    ) d
UNION ALL
SELECT
    'missing_review','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE review_score IS NULL
UNION ALL
SELECT
    'missing_items','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE item_count = 0
UNION ALL
SELECT
    'missing_payments','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE payment_count = 0
UNION ALL
SELECT
    'payment_item_difference','warning',
    COUNT(*)
    FROM olist_bi.order_mart
    WHERE abs(payment_value - item_value - freight_value) > 0.01
UNION ALL
SELECT
    'null_item_amounts','warning',
    COUNT(*)
    FROM olist_raw.items
    WHERE price IS NULL
        OR freight_value IS NULL
UNION ALL
SELECT
    'null_payment_amounts','warning',
    COUNT(*)
    FROM olist_raw.payments
    WHERE payment_value IS NULL
ORDER BY severity, check_name;