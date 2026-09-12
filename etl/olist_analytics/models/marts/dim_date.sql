-- Dimension: one row per calendar day, spanning the full range of order
-- purchase dates. Built with generate_series() directly -- no need for the
-- dbt_utils package just for this.

with date_spine as (
    select generate_series(
        (select min(date_trunc('day', order_purchase_timestamp)) from {{ ref('stg_orders') }}),
        (select max(date_trunc('day', order_purchase_timestamp)) from {{ ref('stg_orders') }}),
        interval '1 day'
    )::date as date_day
)

select
    date_day,
    extract(year from date_day)::int as year,
    extract(month from date_day)::int as month,
    trim(to_char(date_day, 'Month')) as month_name,
    extract(day from date_day)::int as day_of_month,
    extract(dow from date_day)::int as day_of_week,  -- 0 = Sunday, 6 = Saturday
    extract(quarter from date_day)::int as quarter,
    extract(dow from date_day) in (0, 6) as is_weekend
from date_spine