USE ecommerce_portfolio_v2;

CREATE OR REPLACE VIEW v_repeat_windows AS
SELECT w.window_days,
       SUM(TIMESTAMPDIFF(SECOND,f.first_order_date,a.asof_ts)>=w.window_days*86400)
         AS eligible_buyers,
       SUM(TIMESTAMPDIFF(SECOND,f.first_order_date,a.asof_ts)>=w.window_days*86400
           AND EXISTS (
             SELECT 1 FROM v_valid_orders o
             WHERE o.user_id=f.user_id
               AND (o.order_date>f.first_order_date OR
                    (o.order_date=f.first_order_date AND o.order_id>f.first_order_id))
               AND o.order_date<=DATE_ADD(f.first_order_date,INTERVAL w.window_days DAY)
           )) AS repeat_buyers
FROM v_first_orders f
CROSS JOIN (SELECT MAX(order_date) AS asof_ts FROM orders) a
CROSS JOIN (SELECT 7 AS window_days UNION ALL SELECT 15 UNION ALL SELECT 30
            UNION ALL SELECT 60 UNION ALL SELECT 90) w
GROUP BY w.window_days;

CREATE OR REPLACE VIEW v_experiment_sample_size AS
WITH baseline AS (
  SELECT repeat_buyers/eligible_buyers AS p1
  FROM v_repeat_windows WHERE window_days=30
), targets AS (
  SELECT 0.05 AS relative_lift UNION ALL SELECT 0.10
  UNION ALL SELECT 0.20 UNION ALL SELECT 0.30
), p AS (
  SELECT relative_lift,p1,p1*(1+relative_lift) AS p2
  FROM targets CROSS JOIN baseline
), n AS (
  SELECT relative_lift,p1,p2,p2-p1 AS absolute_lift,
    POW(1.95996398454005*SQRT(2*((p1+p2)/2)*(1-(p1+p2)/2))
        +0.841621233572914*SQRT(p1*(1-p1)+p2*(1-p2)),2)
      /POW(p2-p1,2) AS n_unrounded
  FROM p
)
SELECT relative_lift,p1,p2,absolute_lift,
       CEIL(n_unrounded) AS sample_per_arm,
       2*CEIL(n_unrounded) AS sample_total
FROM n;

SELECT window_days,eligible_buyers,repeat_buyers,
       100*repeat_buyers/eligible_buyers AS repeat_rate_pct
FROM v_repeat_windows ORDER BY window_days;

SELECT relative_lift,p1,p2,absolute_lift,sample_per_arm,sample_total
FROM v_experiment_sample_size ORDER BY relative_lift;

-- Design only. No coupon assignment, treatment log, cost or profit data exists.
-- A real experiment must randomize by user_id, run arms concurrently, then
-- assess 30-day repeat purchase plus refund, AOV and actual margin guardrails.
