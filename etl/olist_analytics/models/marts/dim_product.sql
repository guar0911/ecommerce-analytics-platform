-- Dimension: one row per product, with the English category name resolved.

with products as (
    select * from {{ ref('stg_products') }}
),

category_translation as (
    select * from {{ ref('stg_product_category_translation') }}
)

select
    products.product_id,
    products.product_category_name,
    category_translation.product_category_name_en,
    products.product_weight_g,
    products.product_length_cm,
    products.product_height_cm,
    products.product_width_cm,
    products.product_photos_qty
from products
left join category_translation
    on products.product_category_name = category_translation.product_category_name