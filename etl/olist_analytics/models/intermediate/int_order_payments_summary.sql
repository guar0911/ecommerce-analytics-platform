-- Intermediate model: collapse order_payments (multiple rows per order --
-- e.g. a customer splitting payment across a voucher and a credit card)
-- into exactly one row per order.
--
-- Why: downstream fact/dim models join at the order level. If we joined
-- the raw order_payments table directly, an order paid with two methods
-- would fan out into two rows and silently double-count revenue in any
-- aggregation built on top. Summarizing once here gives every downstream
-- model a safe, single row per order_id to join against.

with order_payments as (
    select * from {{ ref('stg_order_payments') }}
),

summary as (
    select
        order_id,
        sum(payment_value) as total_payment_value,
        count(distinct payment_type) as payment_methods_count,
        max(payment_installments) as max_installments
    from order_payments
    group by order_id
)

select * from summary