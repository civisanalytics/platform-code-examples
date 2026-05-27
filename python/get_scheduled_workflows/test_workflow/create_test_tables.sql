DROP TABLE IF EXISTS scratch.test_customers;
CREATE TABLE scratch.test_customers AS
SELECT 1 AS customer_id, 'Alice' AS name, 'alice@example.com' AS email
UNION ALL
SELECT 2, 'Bob', 'bob@example.com'
UNION ALL
SELECT 3, 'Carol', 'carol@example.com';

DROP TABLE IF EXISTS scratch.test_orders;
CREATE TABLE scratch.test_orders AS
SELECT 1 AS order_id, 1 AS customer_id, 100.00 AS amount, '2026-01-01'::date AS order_date
UNION ALL
SELECT 2, 1, 250.00, '2026-01-15'::date
UNION ALL
SELECT 3, 2,  75.00, '2026-02-01'::date
UNION ALL
SELECT 4, 3, 300.00, '2026-02-10'::date;
