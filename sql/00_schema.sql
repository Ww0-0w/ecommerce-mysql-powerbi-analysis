-- Run against a MySQL 8.0 server. A fresh, deliberately named database is required.
CREATE DATABASE ecommerce_portfolio_v2
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE ecommerce_portfolio_v2;

CREATE TABLE users (
  user_id VARCHAR(16) PRIMARY KEY,
  age SMALLINT NULL, gender VARCHAR(16) NULL,
  province VARCHAR(64) NULL, city VARCHAR(64) NULL,
  registration_date DATETIME(6) NULL,
  member_level VARCHAR(32) NULL,
  account_balance DECIMAL(14,2) NULL,
  credit_score SMALLINT NULL
) ENGINE=InnoDB;

CREATE TABLE products (
  product_id VARCHAR(16) PRIMARY KEY,
  product_name VARCHAR(255) NULL,
  category VARCHAR(64) NULL,
  brand VARCHAR(64) NULL,
  price DECIMAL(14,2) NULL,
  sales_count INT NULL
) ENGINE=InnoDB;

CREATE TABLE orders (
  order_id VARCHAR(16) PRIMARY KEY,
  user_id VARCHAR(16) NOT NULL,
  product_id VARCHAR(16) NOT NULL,
  quantity INT NULL,
  order_date DATETIME(6) NOT NULL,
  order_status VARCHAR(32) NOT NULL,
  payment_method VARCHAR(32) NULL,
  unit_price DECIMAL(14,2) NULL,
  total_amount DECIMAL(16,2) NULL,
  discount DECIMAL(16,2) NULL,
  actual_payment DECIMAL(16,2) NULL,
  delivery_date DATETIME(6) NULL,
  receive_date DATETIME(6) NULL,
  review_score TINYINT NULL,
  review_content TEXT NULL,
  KEY idx_orders_user_date (user_id,order_date,order_id),
  KEY idx_orders_product (product_id),
  KEY idx_orders_status_date (order_status,order_date)
) ENGINE=InnoDB;

CREATE TABLE user_behaviors (
  behavior_id VARCHAR(16) PRIMARY KEY,
  user_id VARCHAR(16) NOT NULL,
  product_id VARCHAR(16) NOT NULL,
  behavior_type VARCHAR(32) NOT NULL,
  behavior_time DATETIME(6) NOT NULL,
  duration_seconds INT NULL,
  KEY idx_behavior_user_time (user_id,behavior_time),
  KEY idx_behavior_product (product_id)
) ENGINE=InnoDB;

-- These two source feature tables are loaded for provenance and auditing.
-- Analysis recomputes its metrics from orders instead of trusting these fields.
CREATE TABLE user_features (
  user_id VARCHAR(16) PRIMARY KEY,
  total_spent DOUBLE NULL,
  order_count DOUBLE NULL,
  completed_orders DOUBLE NULL,
  avg_order_amount DOUBLE NULL,
  browse_count DOUBLE NULL,
  click_count DOUBLE NULL,
  favorite_count DOUBLE NULL,
  cart_count DOUBLE NULL,
  days_since_last_order INT NULL,
  order_frequency DOUBLE NULL,
  repurchase_indicator TINYINT NULL,
  purchase_intent DOUBLE NULL,
  consumption_level VARCHAR(32) NULL,
  member_level_score INT NULL
) ENGINE=InnoDB;

CREATE TABLE product_features (
  product_id VARCHAR(16) PRIMARY KEY,
  total_revenue DOUBLE NULL,
  total_sales DOUBLE NULL,
  completed_count INT NULL,
  cancel_count INT NULL,
  `加购_count` INT NULL,
  `收藏_count` INT NULL,
  `浏览_count` INT NULL,
  `点击_count` INT NULL,
  conversion_rate DOUBLE NULL,
  avg_review_score DOUBLE NULL,
  popularity_score DOUBLE NULL
) ENGINE=InnoDB;
