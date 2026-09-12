-- Intermediate model: collapse the raw geolocation table (many lat/lng
-- rows per zip_code_prefix, by design) into exactly one row per zip.
--
-- Why here and not in staging: deciding HOW to pick a single representative
-- point/city/state for a zip code is a business decision, not just type or
-- name cleanup -- that's what separates staging from intermediate.
--
-- Why here and not in marts: more than one downstream model (dim_geography,
-- and possibly a future "sales by region" mart) will need this same
-- deduplicated lookup. Building it once here means every mart just joins
-- against a clean table, instead of repeating this aggregation logic
-- (and risking each mart aggregating it slightly differently).

with geolocation as (
    select * from {{ ref('stg_geolocation') }}
),

aggregated as (
    select
        zip_code_prefix,
        avg(lat) as lat,
        avg(lng) as lng,
        -- multiple city/state spellings can exist for the same zip
        -- (typos, abbreviations); take the most frequent one so the
        -- result is a single, consistent label instead of an arbitrary pick
        mode() within group (order by city) as city,
        mode() within group (order by state) as state
    from geolocation
    group by zip_code_prefix
)

select * from aggregated