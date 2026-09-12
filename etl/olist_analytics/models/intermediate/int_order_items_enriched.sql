-- Intermediate model: enrich each order item with product category
-- (English name) and seller state -- attributes needed by more than one
-- downstream mart (e.g. a sales fact table AND a "top categories" analysis).
--
-- Why here and not in marts: centralizing this join means we write the
-- product/seller join logic once, instead of repeating it in every mart
-- model that needs item-level detail. If the join logic ever needs to
-- change (e.g. handling products with no category differently), there's
-- exactly one place to fix it.

with order_items as (
    select * from {{ ref('stg_order_items') }}
),

products as (
    select * from {{ ref('stg_products') }}
),

category_translation as (
    select * from {{ ref('stg_product_category_translation') }}
),

sellers as (
    select * from {{ ref('stg_sellers') }}
),

enriched as (
    select
        order_items.order_id,
        order_items.order_item_id,
        order_items.product_id,
        order_items.seller_id,
        order_items.shipping_limit_date,
        order_items.price,
        order_items.freight_value,
        category_translation.product_category_name_en,
        sellers.state as seller_state
    from order_items
    left join products
        on order_items.product_id = products.product_id
    left join category_translation
        on products.product_category_name = category_translation.product_category_name
    left join sellers
        on order_items.seller_id = sellers.seller_id
)

select * from enriched