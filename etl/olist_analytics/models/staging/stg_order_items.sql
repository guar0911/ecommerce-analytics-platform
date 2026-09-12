-- Staging model: light cleanup of the raw `order_items` table.

select
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value
from {{ source('olist_oltp', 'order_items') }}
