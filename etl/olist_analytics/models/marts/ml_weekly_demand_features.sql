-- Weekly demand aggregation per product category.
-- Grain: one row per (week_start, product_category_name_en).
-- Lag features and train/test split are built in Python (mlops/src/train_demand_forecast.py) --
-- this model only handles the aggregation, which belongs in the warehouse.

with orders as (
    select * from {{ ref('fact_orders') }}
),

dates as (
    select * from {{ ref('dim_date') }}
),

weekly as (
    select
        date_trunc('week', d.date_day)::date as week_start,
        o.product_category_name_en,
        count(distinct o.order_id) as orders,
        count(*) as items_sold,
        sum(o.price) as revenue
    from orders o
    join dates d on o.order_date = d.date_day
    where o.product_category_name_en is not null
    group by 1, 2
)

select * from weekly
order by week_start, product_category_name_en