-- Olist e-commerce OLTP schema (3NF)
-- Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
-- Place this file at: oltp/schema.sql

-- Lookup table: product category name translation (Portuguese -> English)
CREATE TABLE product_category_translation (
    product_category_name          VARCHAR(100) PRIMARY KEY,
    product_category_name_english  VARCHAR(100) NOT NULL
);

-- Customers who place orders.
-- Note: customer_id is unique PER ORDER in Olist's raw model;
-- customer_unique_id identifies the actual person across multiple orders.
CREATE TABLE customers (
    customer_id                VARCHAR(32) PRIMARY KEY,
    customer_unique_id         VARCHAR(32) NOT NULL,
    customer_zip_code_prefix   VARCHAR(5)  NOT NULL,
    customer_city              VARCHAR(100) NOT NULL,
    customer_state             CHAR(2) NOT NULL
);

CREATE INDEX idx_customers_unique_id ON customers (customer_unique_id);
CREATE INDEX idx_customers_zip       ON customers (customer_zip_code_prefix);

-- Sellers who fulfill order items
CREATE TABLE sellers (
    seller_id               VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix  VARCHAR(5)  NOT NULL,
    seller_city             VARCHAR(100) NOT NULL,
    seller_state            CHAR(2) NOT NULL
);

CREATE INDEX idx_sellers_zip ON sellers (seller_zip_code_prefix);

-- Products catalog
CREATE TABLE products (
    product_id                     VARCHAR(32) PRIMARY KEY,
    product_category_name          VARCHAR(100) REFERENCES product_category_translation (product_category_name),
    product_name_length            SMALLINT,
    product_description_length     INTEGER,
    product_photos_qty             SMALLINT,
    product_weight_g               INTEGER,
    product_length_cm              INTEGER,
    product_height_cm              INTEGER,
    product_width_cm               INTEGER
);

CREATE INDEX idx_products_category ON products (product_category_name);

-- Raw geolocation lookup.
-- Kept intentionally denormalized: Olist ships multiple lat/lng pairs per
-- zip code prefix, so there is no natural single-row key to enforce a strict FK.
CREATE TABLE geolocation (
    geolocation_id               BIGSERIAL PRIMARY KEY,
    geolocation_zip_code_prefix  VARCHAR(5) NOT NULL,
    geolocation_lat              NUMERIC(10, 7) NOT NULL,
    geolocation_lng              NUMERIC(10, 7) NOT NULL,
    geolocation_city             VARCHAR(100) NOT NULL,
    geolocation_state            CHAR(2) NOT NULL
);

CREATE INDEX idx_geolocation_zip ON geolocation (geolocation_zip_code_prefix);

-- Orders placed by customers
CREATE TABLE orders (
    order_id                        VARCHAR(32) PRIMARY KEY,
    customer_id                     VARCHAR(32) NOT NULL REFERENCES customers (customer_id),
    order_status                    VARCHAR(20) NOT NULL,
    order_purchase_timestamp        TIMESTAMP NOT NULL,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP NOT NULL
);

CREATE INDEX idx_orders_customer_id         ON orders (customer_id);
CREATE INDEX idx_orders_purchase_timestamp  ON orders (order_purchase_timestamp);
CREATE INDEX idx_orders_status              ON orders (order_status);

-- Line items within an order (grain: one row per product per order)
CREATE TABLE order_items (
    order_id              VARCHAR(32) NOT NULL REFERENCES orders (order_id),
    order_item_id         SMALLINT NOT NULL,
    product_id            VARCHAR(32) NOT NULL REFERENCES products (product_id),
    seller_id             VARCHAR(32) NOT NULL REFERENCES sellers (seller_id),
    shipping_limit_date   TIMESTAMP NOT NULL,
    price                 NUMERIC(10, 2) NOT NULL,
    freight_value         NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE INDEX idx_order_items_product_id ON order_items (product_id);
CREATE INDEX idx_order_items_seller_id  ON order_items (seller_id);

-- Payments for an order (an order can be paid with multiple installments/methods)
CREATE TABLE order_payments (
    order_id               VARCHAR(32) NOT NULL REFERENCES orders (order_id),
    payment_sequential     SMALLINT NOT NULL,
    payment_type           VARCHAR(20) NOT NULL,
    payment_installments   SMALLINT NOT NULL,
    payment_value          NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE INDEX idx_order_payments_order_id ON order_payments (order_id);

-- Customer reviews for an order
CREATE TABLE order_reviews (
    review_id                 VARCHAR(32) PRIMARY KEY,
    order_id                  VARCHAR(32) NOT NULL REFERENCES orders (order_id),
    review_score              SMALLINT NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title      VARCHAR(255),
    review_comment_message    TEXT,
    review_creation_date      TIMESTAMP NOT NULL,
    review_answer_timestamp   TIMESTAMP
);

CREATE INDEX idx_order_reviews_order_id ON order_reviews (order_id);