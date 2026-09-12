-- Staging model: light cleanup of the raw `product_category_translation` table.

select
    product_category_name,
    product_category_name_english as product_category_name_en
from {{ source('olist_oltp', 'product_category_translation') }}
