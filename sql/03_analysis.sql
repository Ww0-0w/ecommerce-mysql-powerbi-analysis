USE ecommerce_portfolio_v2;

-- 1. Scope and central tendency. MySQL 8 has no built-in MEDIAN aggregate.
SELECT COUNT(*) AS valid_orders,COUNT(DISTINCT user_id) AS buyers,
       SUM(actual_payment) AS gmv,AVG(actual_payment) AS aov,
       AVG(quantity) AS units_per_order
FROM v_valid_orders;

WITH ranked AS (
  SELECT actual_payment,ROW_NUMBER() OVER (ORDER BY actual_payment,order_id) AS rn,
         COUNT(*) OVER () AS n FROM v_valid_orders
)
SELECT AVG(actual_payment) AS median_order_payment
FROM ranked WHERE rn IN (FLOOR((n+1)/2),FLOOR((n+2)/2));

-- 2. Month length is explicit. Only October through February is comparable.
SELECT month_key,calendar_days,orders,buyers,gmv,daily_gmv,aov,
       100*(gmv/LAG(gmv) OVER (ORDER BY month_key)-1) AS monthly_gmv_mom_pct,
       100*(daily_gmv/LAG(daily_gmv) OVER (ORDER BY month_key)-1) AS daily_gmv_mom_pct
FROM v_monthly_metrics ORDER BY month_key;

-- 3. Three-factor identity: GMV = buyers * orders_per_buyer * AOV.
SELECT month_key,buyers,orders_per_buyer,aov,gmv,
       buyers*orders_per_buyer*aov AS reconstructed_gmv
FROM v_monthly_metrics WHERE month_key IN ('2026-01','2026-02');

-- 4. Concentration and one-time buyer contribution.
WITH category_gmv AS (
  SELECT category,COUNT(*) AS orders,SUM(actual_payment) AS gmv
  FROM v_order_enriched GROUP BY category
)
SELECT category,orders,gmv,100*gmv/SUM(gmv) OVER () AS gmv_share_pct
FROM category_gmv ORDER BY gmv DESC;

SELECT COUNT(*) AS buyers,
       SUM(order_count=1) AS one_time_buyers,
       100*SUM(order_count=1)/COUNT(*) AS one_time_buyer_pct,
       100*SUM(CASE WHEN order_count>1 THEN total_spent ELSE 0 END)/SUM(total_spent)
         AS repeat_buyer_gmv_pct
FROM v_user_purchase;

-- 5. RFM thresholds and groups. Tied scores use user_id as a stable tie-breaker.
SELECT r_score,MAX(recency_days) AS max_recency_days,
       f_score,MAX(order_count) AS max_frequency,
       m_score,MAX(total_spent) AS max_monetary
FROM v_rfm_scored GROUP BY r_score,f_score,m_score ORDER BY r_score,f_score,m_score;

SELECT segment,COUNT(*) AS buyers,SUM(total_spent) AS gmv,
       AVG(total_spent) AS avg_spend,AVG(order_count) AS avg_orders,
       100*COUNT(*)/(SELECT COUNT(*) FROM v_rfm_segment) AS buyer_share_pct,
       100*SUM(total_spent)/(SELECT SUM(total_spent) FROM v_rfm_segment) AS gmv_share_pct
FROM v_rfm_segment GROUP BY segment ORDER BY gmv DESC;
