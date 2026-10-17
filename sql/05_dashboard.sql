USE ecommerce_portfolio_v2;

-- Every exported dashboard relation is aggregated. No user or order rows leave MySQL.
CREATE OR REPLACE VIEW dashboard_overview AS
SELECT COUNT(*) AS valid_orders,COUNT(DISTINCT user_id) AS buyers,
       SUM(actual_payment) AS gmv,AVG(actual_payment) AS aov,
       AVG(quantity) AS units_per_order,
       (SELECT COUNT(*) FROM orders) AS source_orders,
       (SELECT COUNT(*) FROM orders WHERE order_status IN ('已取消','已退款','待付款'))
         AS excluded_orders
FROM v_valid_orders;

CREATE OR REPLACE VIEW dashboard_monthly AS
SELECT month_key,calendar_days,orders,buyers,gmv,daily_gmv,aov,
       orders_per_buyer,
       100*(gmv/LAG(gmv) OVER (ORDER BY month_key)-1) AS monthly_gmv_mom_pct,
       100*(daily_gmv/LAG(daily_gmv) OVER (ORDER BY month_key)-1) AS daily_gmv_mom_pct
FROM v_monthly_metrics;

CREATE OR REPLACE VIEW dashboard_categories AS
SELECT category,COUNT(*) AS orders,SUM(actual_payment) AS gmv,
       100*SUM(actual_payment)/(SELECT SUM(actual_payment) FROM v_valid_orders)
         AS gmv_share_pct
FROM v_order_enriched GROUP BY category;

CREATE OR REPLACE VIEW dashboard_rfm AS
SELECT segment,COUNT(*) AS buyers,SUM(total_spent) AS gmv,
       AVG(total_spent) AS avg_spend,AVG(order_count) AS avg_orders,
       100*COUNT(*)/(SELECT COUNT(*) FROM v_rfm_segment) AS buyer_share_pct,
       100*SUM(total_spent)/(SELECT SUM(total_spent) FROM v_rfm_segment) AS gmv_share_pct
FROM v_rfm_segment GROUP BY segment;

CREATE OR REPLACE VIEW dashboard_repeat AS
SELECT window_days,eligible_buyers,repeat_buyers,
       100*repeat_buyers/eligible_buyers AS repeat_rate_pct
FROM v_repeat_windows;

CREATE OR REPLACE VIEW dashboard_experiment AS
SELECT 100*relative_lift AS relative_lift_pct,100*p1 AS baseline_pct,
       100*p2 AS target_pct,100*absolute_lift AS absolute_lift_pp,
       sample_per_arm,sample_total
FROM v_experiment_sample_size;
