-- =============================================================
-- Star schema exploration queries
-- Run these against the `analytics` schema (dbt marts).
-- =============================================================

-- 1. Top 10 categorías por revenue
SELECT
    product_category_name_en,
    COUNT(DISTINCT order_id) AS orders,
    SUM(price) AS revenue
FROM analytics.fact_orders
GROUP BY 1
ORDER BY revenue DESC
LIMIT 10;

-- 2. Revenue mensual (tendencia de ventas)
SELECT
    d.year,
    d.month,
    SUM(f.price) AS revenue,
    COUNT(DISTINCT f.order_id) AS orders
FROM analytics.fact_orders f
JOIN analytics.dim_date d ON f.order_date = d.date_day
GROUP BY 1, 2
ORDER BY 1, 2;

-- 3. Top 10 vendedores por revenue
SELECT
    f.seller_id,
    s.state AS seller_state,
    COUNT(DISTINCT f.order_id) AS orders,
    SUM(f.price) AS revenue
FROM analytics.fact_orders f
JOIN analytics.dim_seller s ON f.seller_id = s.seller_id
GROUP BY 1, 2
ORDER BY revenue DESC
LIMIT 10;

-- 4. Tiempo promedio de entrega por estado del cliente (en días)
SELECT
    c.state AS customer_state,
    ROUND(AVG(
        EXTRACT(EPOCH FROM (f.order_delivered_customer_date - f.order_purchase_timestamp)) / 86400
    )::numeric, 1) AS avg_delivery_days,
    COUNT(*) AS delivered_orders
FROM analytics.fact_orders f
JOIN analytics.dim_customer c ON f.customer_id = c.customer_id
WHERE f.order_delivered_customer_date IS NOT NULL
GROUP BY 1
ORDER BY avg_delivery_days DESC;

-- 5. Distribución de pedidos por status
SELECT
    order_status,
    COUNT(DISTINCT order_id) AS orders
FROM analytics.fact_orders
GROUP BY 1
ORDER BY orders DESC;

-- 6. Clientes por estado (dónde está concentrada la base de clientes)
SELECT
    state,
    COUNT(*) AS customers
FROM analytics.dim_customer
GROUP BY 1
ORDER BY customers DESC
LIMIT 10;

-- 7. Ticket promedio por método de pago (usando la métrica a nivel de PEDIDO,
--    no de línea de pedido -- por eso deduplicamos por order_id primero,
--    ver la nota sobre order_total_payment_value en fact_orders.sql)
SELECT
    payment_methods_count,
    ROUND(AVG(order_total_payment_value)::numeric, 2) AS avg_order_value,
    COUNT(DISTINCT order_id) AS orders
FROM (
    SELECT DISTINCT ON (order_id)
        order_id,
        payment_methods_count,
        order_total_payment_value
    FROM analytics.fact_orders
) AS one_row_per_order
GROUP BY 1
ORDER BY 1;