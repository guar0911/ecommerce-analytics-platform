-- Fact table. Grain: one row per order line item (order_id + order_item_id).
--
-- IMPORTANT MODELING NOTE on order_total_payment_value:
-- Payments live at the ORDER level (int_order_payments_summary), but this
-- fact table lives at the ORDER ITEM level. That means order_total_payment_value
-- is repeated identically across every item belonging to the same order.
-- Never SUM(order_total_payment_value) directly in a query on this table --
-- you'll multiply the real total by however many items the order has.
-- If you need total revenue paid, either aggregate from
-- int_order_payments_summary directly, or dedupe by order_id first.

with order_items as (
    select * from {{ ref('int_order_items_enriched') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

payments as (
    select * from {{ ref('int_order_payments_summary') }}
)

select
    -- keys
    order_items.order_id,
    order_items.order_item_id,
    orders.customer_id,
    order_items.product_id,
    order_items.seller_id,
    orders.order_purchase_timestamp::date as order_date,  -- FK to dim_date.date_day

    -- order-level attributes (repeated per item -- see note above)
    orders.order_status,
    orders.order_purchase_timestamp,
    orders.order_delivered_customer_date,
    orders.order_estimated_delivery_date,
    payments.total_payment_value as order_total_payment_value,
    payments.payment_methods_count,
    payments.max_installments,

    -- item-level metrics (safe to sum/aggregate freely)
    order_items.price,
    order_items.freight_value,
    order_items.price + order_items.freight_value as item_total,

    -- denormalized attributes, handy for quick filtering without extra joins
    order_items.product_category_name_en,
    order_items.seller_state

from order_items
left join orders
    on order_items.order_id = orders.order_id
left join payments
    on order_items.order_id = payments.order_id