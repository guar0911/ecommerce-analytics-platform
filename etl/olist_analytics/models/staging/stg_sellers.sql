-- Staging model: light cleanup of the raw `sellers` table.

select
    seller_id,
    seller_zip_code_prefix as zip_code_prefix,
    seller_city as city,
    seller_state as state
from {{ source('olist_oltp', 'sellers') }}
