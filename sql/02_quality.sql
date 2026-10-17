USE ecommerce_portfolio_v2;

-- An auditable checklist. A nonzero issue count should be investigated before analysis.
CREATE OR REPLACE VIEW v_quality_checks AS
SELECT 'users_rows' AS check_name,COUNT(*) AS observed,5000 AS expected FROM users
UNION ALL SELECT 'products_rows',COUNT(*),2000 FROM products
UNION ALL SELECT 'orders_rows',COUNT(*),15000 FROM orders
UNION ALL SELECT 'behaviors_rows',COUNT(*),30000 FROM user_behaviors
UNION ALL SELECT 'user_features_rows',COUNT(*),5000 FROM user_features
UNION ALL SELECT 'product_features_rows',COUNT(*),2000 FROM product_features
UNION ALL SELECT 'order_orphan_users',COUNT(*),0
  FROM orders o LEFT JOIN users u ON u.user_id=o.user_id WHERE u.user_id IS NULL
UNION ALL SELECT 'order_orphan_products',COUNT(*),0
  FROM orders o LEFT JOIN products p ON p.product_id=o.product_id WHERE p.product_id IS NULL
UNION ALL SELECT 'behavior_orphan_users',COUNT(*),0
  FROM user_behaviors b LEFT JOIN users u ON u.user_id=b.user_id WHERE u.user_id IS NULL
UNION ALL SELECT 'behavior_orphan_products',COUNT(*),0
  FROM user_behaviors b LEFT JOIN products p ON p.product_id=b.product_id WHERE p.product_id IS NULL
UNION ALL SELECT 'amount_identity_failures',COUNT(*),0
  FROM orders WHERE ABS(total_amount-discount-actual_payment)>0.01
UNION ALL SELECT 'invalid_money_or_quantity',COUNT(*),0
  FROM orders WHERE actual_payment<0 OR quantity<=0 OR actual_payment IS NULL
UNION ALL SELECT 'stale_last_order_feature',COUNT(*),5000
  FROM user_features WHERE days_since_last_order=999
UNION ALL SELECT 'review_score_missing',COUNT(*),10777
  FROM orders WHERE review_score IS NULL
UNION ALL SELECT 'excluded_orders',COUNT(*),2235
  FROM orders WHERE order_status IN ('已取消','已退款','待付款')
UNION ALL SELECT 'valid_orders',COUNT(*),12765 FROM v_valid_orders;

SELECT check_name,observed,expected,
       IF(observed=expected,'PASS','FAIL') AS result
FROM v_quality_checks ORDER BY check_name;

-- Diagnostic, not a failure: source quantity * unit_price usually differs from total_amount.
SELECT COUNT(*) AS source_orders,
       SUM(ABS(quantity*unit_price-total_amount)<=0.01) AS quantity_price_matches,
       SUM(review_score IS NULL) AS missing_reviews,
       MIN(order_date) AS first_order_ts,MAX(order_date) AS last_order_ts
FROM orders;

SELECT order_status,COUNT(*) AS order_count,SUM(actual_payment) AS source_payment
FROM orders GROUP BY order_status ORDER BY order_count DESC;
