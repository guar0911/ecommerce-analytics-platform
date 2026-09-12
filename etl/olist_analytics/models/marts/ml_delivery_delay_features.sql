-- Feature table for the delivery delay classification model.
-- Grain: one row per order (not per item -- delay is an order-level outcome).
-- Only includes delivered orders, since is_late requires an actual delivery date.

with orders as (
    select * from {{ ref('fact_orders') }}
),

customers as (
    select * from {{ ref('dim_customer') }}
),

sellers as (
    select * from {{ ref('dim_seller') }}
),

customer_geo as (
    select * from {{ ref('dim_geography') }}
),

seller_geo as (
    select * from {{ ref('dim_geography') }}
),

dates as (
    select * from {{ ref('dim_date') }}
),

-- Collapse item-level fact_orders to one row per order.
-- Note: if an order has items from more than one seller (rare), we just take
-- the first seller_id -- acceptable simplification for a v1 model.
order_level as (
    select
        order_id,
        customer_id,
        min(seller_id) as seller_id,
        order_purchase_timestamp,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        sum(price) as order_price,
        sum(freight_value) as order_freight_value,
        count(*) as item_count,
        max(order_total_payment_value) as order_total_payment_value,
        max(payment_methods_count) as payment_methods_count,
        max(max_installments) as max_installments,
        min(product_category_name_en) as product_category_name_en
    from orders
    where order_status = 'delivered'
      and order_delivered_customer_date is not null
    group by
        order_id, customer_id, order_purchase_timestamp,
        order_delivered_customer_date, order_estimated_delivery_date
)

select
    ol.order_id,
    ol.customer_id,
    ol.seller_id,

    -- time features
    d.month,
    d.day_of_week,
    d.is_weekend,

    -- geography
    c.state as customer_state,
    s.state as seller_state,
    -- Haversine distance (km) between seller and customer zip centroids
    2 * 6371 * asin(
        sqrt(
            power(sin(radians(cg.lat - sg.lat) / 2), 2)
            + cos(radians(sg.lat)) * cos(radians(cg.lat))
            * power(sin(radians(cg.lng - sg.lng) / 2), 2)
        )
    ) as seller_customer_distance_km,

    -- order-level metrics
    ol.order_price,
    ol.order_freight_value,
    ol.item_count,
    ol.order_total_payment_value,
    ol.payment_methods_count,
    ol.max_installments,
    ol.product_category_name_en,

    -- label
    case
        when ol.order_delivered_customer_date > ol.order_estimated_delivery_date
        then 1 else 0
    end as is_late

from order_level ol
left join customers c on ol.customer_id = c.customer_id
left join sellers s on ol.seller_id = s.seller_id
left join customer_geo cg on c.zip_code_prefix = cg.zip_code_prefix
left join seller_geo sg on s.zip_code_prefix = sg.zip_code_prefix
left join dates d on ol.order_purchase_timestamp::date = d.date_day