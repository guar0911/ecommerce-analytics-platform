-- Staging model: light cleanup of the raw `products` table.
-- Column names were already fixed at load time (product_name_lenght -> _length),
-- so this is mostly an explicit column list rather than renames.

select
    product_id,
    product_category_name,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
from {{ source('olist_oltp', 'products') }}
