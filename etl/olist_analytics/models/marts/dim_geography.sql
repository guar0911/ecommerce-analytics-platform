-- Dimension: one row per zip code, with representative lat/lng/city/state.
-- Built directly on the intermediate model that already collapsed the raw
-- geolocation table to one row per zip -- no aggregation logic repeated here.

select
    zip_code_prefix,
    lat,
    lng,
    city,
    state
from {{ ref('int_geolocation_aggregated') }}