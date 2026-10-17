USE ecommerce_portfolio_v2;

CREATE OR REPLACE VIEW v_valid_orders AS
SELECT * FROM orders
WHERE order_status NOT IN ('已取消','已退款','待付款');

CREATE OR REPLACE VIEW v_order_enriched AS
SELECT o.order_id,o.user_id,o.product_id,o.quantity,o.order_date,
       o.order_status,o.actual_payment,p.category,p.brand
FROM v_valid_orders o JOIN products p ON p.product_id=o.product_id;

CREATE OR REPLACE VIEW v_user_purchase AS
SELECT o.user_id,MIN(o.order_date) AS first_order_date,
       MAX(o.order_date) AS last_order_date,
       COUNT(*) AS order_count,
       SUM(o.actual_payment) AS total_spent,
       AVG(o.actual_payment) AS avg_order_amount,
       TIMESTAMPDIFF(SECOND,MAX(o.order_date),a.asof_ts)/86400.0 AS recency_days
FROM v_valid_orders o CROSS JOIN (SELECT MAX(order_date) AS asof_ts FROM orders) a
GROUP BY o.user_id,a.asof_ts;

-- NTILE splits tied F values deterministically by user_id. R=1 is least recent.
CREATE OR REPLACE VIEW v_rfm_scored AS
SELECT user_id,first_order_date,last_order_date,order_count,total_spent,
       avg_order_amount,recency_days,
       NTILE(3) OVER (ORDER BY recency_days DESC,user_id) AS r_score,
       NTILE(3) OVER (ORDER BY order_count ASC,user_id) AS f_score,
       NTILE(3) OVER (ORDER BY total_spent ASC,user_id) AS m_score
FROM v_user_purchase;

CREATE OR REPLACE VIEW v_rfm_segment AS
SELECT s.*,
  CASE WHEN r_score>=2 AND f_score>=2 AND m_score>=2 THEN '核心价值客户'
       WHEN r_score<2 AND f_score>=2 AND m_score>=2 THEN '流失风险客户'
       WHEN r_score>=2 THEN '成长潜力客户'
       ELSE '一般客户' END AS segment
FROM v_rfm_scored s;

CREATE OR REPLACE VIEW v_first_orders AS
SELECT user_id,order_id AS first_order_id,order_date AS first_order_date
FROM (
  SELECT user_id,order_id,order_date,
         ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date,order_id) AS rn
  FROM v_valid_orders
) x WHERE rn=1;

CREATE OR REPLACE VIEW v_repeat_cohort AS
SELECT f.user_id,f.first_order_id,f.first_order_date,
       TIMESTAMPDIFF(SECOND,f.first_order_date,a.asof_ts)>=30*86400 AS eligible_30d,
       EXISTS (
         SELECT 1 FROM v_valid_orders o
         WHERE o.user_id=f.user_id
           AND (o.order_date>f.first_order_date OR
                (o.order_date=f.first_order_date AND o.order_id>f.first_order_id))
           AND o.order_date<=DATE_ADD(f.first_order_date,INTERVAL 30 DAY)
       ) AS repeated_30d
FROM v_first_orders f
CROSS JOIN (SELECT MAX(order_date) AS asof_ts FROM orders) a;

CREATE OR REPLACE VIEW v_monthly_metrics AS
SELECT DATE_FORMAT(order_date,'%Y-%m') AS month_key,
       MAX(DAY(LAST_DAY(DATE(order_date)))) AS calendar_days,
       COUNT(*) AS orders,COUNT(DISTINCT user_id) AS buyers,
       SUM(quantity) AS units,SUM(actual_payment) AS gmv,
       SUM(actual_payment)/COUNT(*) AS aov,
       SUM(actual_payment)/MAX(DAY(LAST_DAY(DATE(order_date)))) AS daily_gmv,
       COUNT(*)/COUNT(DISTINCT user_id) AS orders_per_buyer
FROM v_valid_orders
WHERE order_date>='2025-10-01' AND order_date<'2026-03-01'
GROUP BY DATE_FORMAT(order_date,'%Y-%m');
