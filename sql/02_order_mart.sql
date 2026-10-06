-- Grain: exactly one row for every source order, including cancelled orders.
-- Aggregate each one-to-many source BEFORE joining to avoid fan-out.
CREATE OR REPLACE VIEW olist_bi.order_mart AS
WITH item_totals AS (
    SELECT
        i.order_id,
        COUNT(*) AS item_count,
        COUNT(DISTINCT i.seller_id) AS seller_count,
        SUM(i.price) AS item_value,
        SUM(i.freight_value) AS freight_value,
        CASE
            WHEN COUNT(DISTINCT COALESCE(p.product_category_name,'unknown')) = 1
                THEN min(COALESCE(p.product_category_name,'unknown'))
            ELSE 'mixed_categories'
        END AS category
    FROM olist_raw.items i
    JOIN olist_raw.products p
        USING(product_id)
    GROUP BY i.order_id
),
payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS payment_value,
        COUNT(*) AS payment_count
    FROM olist_raw.payments
    GROUP BY order_id
),
ranked_reviews AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY review_answer_timestamp DESC NULLS LAST,
                review_creation_date DESC NULLS LAST,
                review_id DESC,
                review_score DESC NULLS LAST
        ) AS rn
    FROM olist_raw.reviews
),
base AS (
    SELECT
        o.*,
        COALESCE(c.customer_state,'unknown') AS customer_state,
        COALESCE(i.category,'no_items') AS category,
        COALESCE(i.item_count,0) AS item_count,
        COALESCE(i.seller_count,0) AS seller_count,
        COALESCE(i.item_value,0) AS item_value,
        COALESCE(i.freight_value,0) AS freight_value,
        COALESCE(p.payment_value,0) AS payment_value,
        COALESCE(p.payment_count,0) AS payment_count,
        r.review_score,
        (
            o.order_purchase_timestamp IS NOT NULL
            AND o.order_delivered_customer_date IS NOT NULL
            AND o.order_delivered_customer_date >= o.order_purchase_timestamp
        ) AS valid_duration,
        (
            o.order_status = 'delivered'
            AND o.order_purchase_timestamp IS NOT NULL
            AND o.order_delivered_customer_date IS NOT NULL
            AND o.order_estimated_delivery_date IS NOT NULL
            AND o.order_delivered_customer_date >= o.order_purchase_timestamp
            AND o.order_estimated_delivery_date::DATE >= o.order_purchase_timestamp::DATE
        ) AS eligible_delivery
    FROM olist_raw.orders o
    JOIN olist_raw.customers c
        USING(customer_id)
    LEFT JOIN item_totals i
        USING(order_id)
    LEFT JOIN payment_totals p
        USING(order_id)
    LEFT JOIN ranked_reviews r
        ON r.order_id = o.order_id
        AND r.rn = 1
)
SELECT
    *,
    date_trunc('month',order_purchase_timestamp)::DATE AS purchase_month,
    CASE
        WHEN eligible_delivery
            THEN order_delivered_customer_date::DATE > order_estimated_delivery_date::DATE
    END AS is_late,
    CASE
        WHEN order_status = 'delivered' AND valid_duration
            THEN EXTRACT(
                epoch FROM (order_delivered_customer_date - order_purchase_timestamp)
            ) / 86400.0
    END AS delivery_days,
    CASE
        WHEN eligible_delivery
            THEN GREATEST(
                0,
                order_delivered_customer_date::DATE - order_estimated_delivery_date::DATE
            )
    END AS days_late,
    CASE
        WHEN review_score IS NOT NULL
            THEN review_score <= 2
    END AS is_low_review
FROM base;