-- Staging model: light cleanup of the raw `geolocation` table.
-- Note: this table has multiple lat/lng rows per zip_code_prefix by design
-- (see oltp/schema.sql). Deduplication/aggregation belongs in a later
-- intermediate or marts model, not here -- staging stays a 1:1 passthrough.

select
    geolocation_zip_code_prefix as zip_code_prefix,
    geolocation_lat as lat,
    geolocation_lng as lng,
    geolocation_city as city,
    geolocation_state as state
from {{ source('olist_oltp', 'geolocation') }}
