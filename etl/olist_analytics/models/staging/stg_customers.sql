-- Staging model: light cleanup of the raw `customers` table.
-- No business logic here yet, just renaming/casting so downstream models
-- have a stable, well-typed interface to build on.

select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix as zip_code_prefix,
    customer_city as city,
    customer_state as state
from {{ source('olist_oltp', 'customers') }}
