-- This file defines the database structure. The tables that will hold orders, customers, items, payments, and the other records

-- Project-specific schemas; never drops public or another application's tables
CREATE SCHEMA IF NOT EXISTS olist_raw;

CREATE SCHEMA IF NOT EXISTS olist_bi;

CREATE TABLE IF NOT EXISTS olist_raw.customers (
    customer_id TEXT PRIMARY KEY, 
    customer_unique_id TEXT, 
    customer_state TEXT);

CREATE TABLE IF NOT EXISTS olist_raw.orders (
    order_id TEXT PRIMARY KEY, 
    customer_id TEXT NOT NULL 
        REFERENCES olist_raw.customers,
    order_status TEXT NOT NULL, order_purchase_TIMESTAMP TIMESTAMP,
    order_approved_at TIMESTAMP, order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP, order_estimated_delivery_date TIMESTAMP);

CREATE TABLE IF NOT EXISTS olist_raw.products (
    product_id TEXT PRIMARY KEY, 
    product_category_name TEXT);

CREATE TABLE IF NOT EXISTS olist_raw.sellers (
    seller_id TEXT PRIMARY KEY, 
    seller_state TEXT);

CREATE TABLE IF NOT EXISTS olist_raw.items (
    order_id TEXT 
        REFERENCES olist_raw.orders, 
    order_item_id INTEGER,
    product_id TEXT NOT NULL 
        REFERENCES olist_raw.products,
    seller_id TEXT NOT NULL 
        REFERENCES olist_raw.sellers,
    shipping_limit_date TIMESTAMP, 
    price NUMERIC(14,2) CHECK(price >= 0),
    freight_value NUMERIC(14,2) CHECK(freight_value >= 0),
    PRIMARY KEY(order_id, order_item_id));

CREATE TABLE IF NOT EXISTS olist_raw.payments (
    order_id TEXT 
        REFERENCES olist_raw.orders, 
    payment_sequential INTEGER,
    payment_type TEXT, 
    payment_installments INTEGER,
    payment_value NUMERIC(14,2) CHECK(payment_value >= 0),
    PRIMARY KEY(order_id, payment_sequential));

-- review_id is NOT assumed to be unique. Multiple reviews may refer to an order.
CREATE TABLE IF NOT EXISTS olist_raw.reviews (
    review_id TEXT NOT NULL, 
    order_id TEXT NOT NULL 
        REFERENCES olist_raw.orders,
    review_score INTEGER CHECK(review_score BETWEEN 1 AND 5),
    review_creation_date TIMESTAMP, review_answer_TIMESTAMP TIMESTAMP);

CREATE INDEX IF NOT EXISTS reviews_order_idx 
    ON olist_raw.reviews(order_id);

CREATE TABLE IF NOT EXISTS olist_bi.run_metadata (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    dataset_label TEXT NOT NULL, 
    loaded_at TIMESTAMPtz NOT NULL DEFAULT now(),
    manifest jsonb NOT NULL);
