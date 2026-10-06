"""Fixed input filenames and selected columns, shared by the loader and test fixtures."""

TABLES = {
    'customers': (
        'olist_customers_dataset.csv',
        [
            'customer_id',
            'customer_unique_id',
            'customer_state',
        ],
    ),
    'orders': (
        'olist_orders_dataset.csv',
        [
            'order_id',
            'customer_id',
            'order_status',
            'order_purchase_timestamp',
            'order_approved_at',
            'order_delivered_carrier_date',
            'order_delivered_customer_date',
            'order_estimated_delivery_date',
        ],
    ),
    'products': (
        'olist_products_dataset.csv',
        [
            'product_id',
            'product_category_name',
        ],
    ),
    'sellers': (
        'olist_sellers_dataset.csv',
        [
            'seller_id',
            'seller_state',
        ],
    ),
    'items': (
        'olist_order_items_dataset.csv',
        [
            'order_id',
            'order_item_id',
            'product_id',
            'seller_id',
            'shipping_limit_date',
            'price',
            'freight_value',
        ],
    ),
    'payments': (
        'olist_order_payments_dataset.csv',
        [
            'order_id',
            'payment_sequential',
            'payment_type',
            'payment_installments',
            'payment_value',
        ],
    ),
    'reviews': (
        'olist_order_reviews_dataset.csv',
        [
            'review_id',
            'order_id',
            'review_score',
            'review_creation_date',
            'review_answer_timestamp',
        ],
    ),
}
