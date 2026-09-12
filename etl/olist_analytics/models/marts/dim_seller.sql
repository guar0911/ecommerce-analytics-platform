-- Dimension: one row per seller.

select
    seller_id,
    zip_code_prefix,
    city,
    state
from {{ ref('stg_sellers') }}