-- Staging model: light cleanup of the raw `order_payments` table.

select
    order_id,
    payment_sequential,
    payment_type,
    payment_installments,
    payment_value
from {{ source('olist_oltp', 'order_payments') }}
