-- =====================================================================
-- Viral to Value - star schema (PostgreSQL syntax; also runs on DuckDB)
-- Fact tables : orders, sessions
-- Dimensions  : campaigns, customers, products
-- =====================================================================

DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS products;

CREATE TABLE products (
    product_id      VARCHAR(10)   PRIMARY KEY,
    product_name    VARCHAR(60)   NOT NULL,
    category        VARCHAR(30)   NOT NULL,
    price           NUMERIC(10,2) NOT NULL CHECK (price > 0),
    cogs            NUMERIC(10,2) NOT NULL CHECK (cogs >= 0),
    launch_date     DATE          NOT NULL
);

CREATE TABLE campaigns (
    campaign_id         VARCHAR(10)   PRIMARY KEY,
    campaign_date       DATE          NOT NULL,
    campaign_name       VARCHAR(80),
    content_type        VARCHAR(20)   NOT NULL,   -- Reel / Carousel / Story / Static Post / Live
    campaign_type       VARCHAR(30)   NOT NULL,   -- Influencer / Product Drop / UGC / Discount / Organic / Paid Amplification
    creator_tier        VARCHAR(10)   NOT NULL,   -- Nano / Micro / Mid / Macro / Mega / Brand
    featured_category   VARCHAR(30),
    spend               NUMERIC(12,2) NOT NULL CHECK (spend >= 0),
    discount_pct        INTEGER       NOT NULL CHECK (discount_pct BETWEEN 0 AND 100),
    reach               BIGINT        NOT NULL,
    impressions         BIGINT        NOT NULL,
    likes               BIGINT        NOT NULL,
    comments            BIGINT        NOT NULL,
    shares              BIGINT        NOT NULL,
    saves               BIGINT        NOT NULL,
    follower_gain       BIGINT        NOT NULL
);

CREATE TABLE customers (
    customer_id           VARCHAR(10) PRIMARY KEY,
    acquisition_date      DATE        NOT NULL,
    acquisition_campaign  VARCHAR(10) NOT NULL REFERENCES campaigns(campaign_id),
    age_group             VARCHAR(10),
    region                VARCHAR(20),
    first_purchase_date   DATE        NOT NULL,
    acquisition_device    VARCHAR(10)
);

CREATE TABLE orders (
    order_id        VARCHAR(12)   PRIMARY KEY,
    customer_id     VARCHAR(10)   NOT NULL REFERENCES customers(customer_id),
    order_date      DATE          NOT NULL,
    product_id      VARCHAR(10)   NOT NULL REFERENCES products(product_id),
    quantity        INTEGER       NOT NULL CHECK (quantity > 0),
    gross_revenue   NUMERIC(12,2) NOT NULL,
    discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_revenue     NUMERIC(12,2) NOT NULL,
    cogs            NUMERIC(12,2) NOT NULL,
    shipping_cost   NUMERIC(12,2) NOT NULL,
    payment_fee     NUMERIC(12,2) NOT NULL,
    refund_amount   NUMERIC(12,2) NOT NULL DEFAULT 0,
    refund_days     INTEGER,                      -- days after order the refund was processed (NULL = none)
    delivery_days   INTEGER,
    is_first_order  INTEGER       NOT NULL CHECK (is_first_order IN (0, 1))
);

CREATE TABLE sessions (
    session_id        VARCHAR(12) PRIMARY KEY,
    customer_id       VARCHAR(10) REFERENCES customers(customer_id),   -- NULL for anonymous visitors
    "timestamp"       TIMESTAMP   NOT NULL,
    campaign_id       VARCHAR(10) REFERENCES campaigns(campaign_id),   -- NULL for non-campaign traffic
    traffic_source    VARCHAR(30) NOT NULL,
    device            VARCHAR(10),
    product_views     INTEGER     NOT NULL,
    add_to_cart       INTEGER     NOT NULL,
    checkout_started  INTEGER     NOT NULL,
    purchase          INTEGER     NOT NULL
);

CREATE INDEX idx_orders_customer  ON orders(customer_id);
CREATE INDEX idx_orders_date      ON orders(order_date);
CREATE INDEX idx_sessions_camp    ON sessions(campaign_id);
CREATE INDEX idx_customers_camp   ON customers(acquisition_campaign);

-- ---------------------------------------------------------------------
-- Loading (PostgreSQL, from psql):
--   \copy products  FROM 'data/raw/products.csv'  CSV HEADER
--   \copy campaigns FROM 'data/raw/campaigns.csv' CSV HEADER
--   \copy customers FROM 'data/raw/customers.csv' CSV HEADER
--   \copy orders    FROM 'data/raw/orders.csv'    CSV HEADER
--   \copy sessions  FROM 'data/raw/sessions.csv'  CSV HEADER
-- DuckDB loading is handled by src/run_sql.py
-- ---------------------------------------------------------------------
