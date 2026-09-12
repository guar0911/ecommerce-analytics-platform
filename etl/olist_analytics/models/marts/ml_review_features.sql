-- Feature table for the negative review classification model.
-- Grain: one row per order. Only delivered orders with a review are included
-- (can't predict a review that doesn't exist yet).
-- Label: is_negative_review = 1 if review_score <= 2.

with orders as (
    select * from {{ ref('fact_orders') }}
),

reviews as (
    select * from {{ ref('stg_order_reviews') }}
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
),

-- Safety net: collapse to one review per order in case any duplicates slipped
-- through (shouldn't happen after the dedup we did at load time).
reviews_agg as (
    select order_id, min(review_score) as review_score
    from reviews
    group by order_id
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

    -- delivery experience features (the likely strongest predictors here)
    extract(epoch from (ol.order_delivered_customer_date - ol.order_purchase_timestamp)) / 86400
        as delivery_days,
    extract(epoch from (ol.order_delivered_customer_date - ol.order_estimated_delivery_date)) / 86400
        as delivery_delta_days,  -- positive = arrived late, negative = arrived early
    case
        when ol.order_delivered_customer_date > ol.order_estimated_delivery_date
        then 1 else 0
    end as was_late,

    -- label
    r.review_score,
    case when r.review_score <= 2 then 1 else 0 end as is_negative_review

from order_level ol
inner join reviews_agg r on ol.order_id = r.order_id
left join customers c on ol.customer_id = c.customer_id
left join sellers s on ol.seller_id = s.seller_id
left join customer_geo cg on c.zip_code_prefix = cg.zip_code_prefix
left join seller_geo sg on s.zip_code_prefix = sg.zip_code_prefix
left join dates d on ol.order_purchase_timestamp::date = d.date_day