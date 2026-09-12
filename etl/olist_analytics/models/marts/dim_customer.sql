-- Dimension: one row per customer.

select
    customer_id,
    customer_unique_id,
    zip_code_prefix,
    city,
    state
from {{ ref('stg_customers') }}