-- ============================================================
-- Oracle 21c XE — Sales / CRM Schema Setup
-- ============================================================
-- Run this script as SYSDBA (SYS or SYSTEM) using SQL*Plus or
-- Oracle SQL Developer connected to the pluggable database XEPDB1.
--
-- How to connect in SQL*Plus:
--   sqlplus sys/YOUR_SYSTEM_PASSWORD@localhost:1521/XEPDB1 as sysdba
--
-- How to connect in SQL Developer:
--   Host: localhost | Port: 1521 | Service Name: XEPDB1
--   Username: SYS | Role: SYSDBA
--
-- This script will:
--   1. Create user BI_SALES with password Baloo100!!or
--   2. Grant all necessary privileges
--   3. Create Sales/CRM tables
--   4. Load ~10,000 rows of realistic sample data
--   5. Create indexes for query performance
-- ============================================================

-- ── STEP 1: Create the Schema User ──────────────────────────
-- Must be run as SYSDBA connected to XEPDB1 (not CDB$ROOT)

ALTER SESSION SET CONTAINER = XEPDB1;

CREATE USER BI_SALES IDENTIFIED BY "Baloo100!!or"
    DEFAULT TABLESPACE USERS
    TEMPORARY TABLESPACE TEMP
    QUOTA UNLIMITED ON USERS;

GRANT CONNECT, RESOURCE TO BI_SALES;
GRANT CREATE SESSION TO BI_SALES;
GRANT CREATE TABLE TO BI_SALES;
GRANT CREATE SEQUENCE TO BI_SALES;
GRANT CREATE VIEW TO BI_SALES;
GRANT CREATE PROCEDURE TO BI_SALES;
GRANT UNLIMITED TABLESPACE TO BI_SALES;

-- Switch to the new schema
ALTER SESSION SET CURRENT_SCHEMA = BI_SALES;

-- ── STEP 2: Create Tables ────────────────────────────────────

-- Regions
CREATE TABLE regions (
    region_id   NUMBER(4)    PRIMARY KEY,
    region_name VARCHAR2(50) NOT NULL,
    country     VARCHAR2(50) NOT NULL
);

-- Sales Representatives (maps to emp_id in Postgres HR)
CREATE TABLE sales_reps (
    rep_id      NUMBER(10)    PRIMARY KEY,
    emp_id      NUMBER(10)    NOT NULL,   -- FK to hr_employees.emp_id in Postgres
    rep_name    VARCHAR2(100) NOT NULL,
    region_id   NUMBER(4)     REFERENCES regions(region_id),
    hire_date   DATE          NOT NULL,
    quota       NUMBER(12,2)  NOT NULL,
    active      CHAR(1)       DEFAULT 'Y' CHECK (active IN ('Y','N'))
);

-- Customers
CREATE TABLE customers (
    customer_id   NUMBER(10)    PRIMARY KEY,
    company_name  VARCHAR2(150) NOT NULL,
    contact_name  VARCHAR2(100),
    email         VARCHAR2(150),
    phone         VARCHAR2(30),
    city          VARCHAR2(80),
    state         VARCHAR2(50),
    country       VARCHAR2(50) DEFAULT 'USA',
    segment       VARCHAR2(30) CHECK (segment IN ('Enterprise','Mid-Market','SMB','Startup')),
    created_date  DATE         NOT NULL
);

-- Products
CREATE TABLE products (
    product_id    NUMBER(10)    PRIMARY KEY,
    product_name  VARCHAR2(150) NOT NULL,
    category      VARCHAR2(60)  NOT NULL,
    unit_price    NUMBER(10,2)  NOT NULL,
    cost          NUMBER(10,2)  NOT NULL,
    active        CHAR(1)       DEFAULT 'Y'
);

-- Orders
CREATE TABLE orders (
    order_id      NUMBER(10)   PRIMARY KEY,
    customer_id   NUMBER(10)   REFERENCES customers(customer_id),
    rep_id        NUMBER(10)   REFERENCES sales_reps(rep_id),
    order_date    DATE         NOT NULL,
    close_date    DATE,
    status        VARCHAR2(20) CHECK (status IN ('Prospecting','Proposal','Negotiation','Won','Lost')),
    deal_value    NUMBER(12,2) NOT NULL,
    region_id     NUMBER(4)    REFERENCES regions(region_id)
);

-- Order Line Items
CREATE TABLE order_items (
    item_id       NUMBER(10)  PRIMARY KEY,
    order_id      NUMBER(10)  REFERENCES orders(order_id),
    product_id    NUMBER(10)  REFERENCES products(product_id),
    quantity      NUMBER(6)   NOT NULL,
    unit_price    NUMBER(10,2) NOT NULL,
    discount_pct  NUMBER(5,2)  DEFAULT 0,
    line_total    NUMBER(12,2) NOT NULL
);

-- Activities / CRM Touchpoints
CREATE TABLE activities (
    activity_id   NUMBER(10)   PRIMARY KEY,
    order_id      NUMBER(10)   REFERENCES orders(order_id),
    rep_id        NUMBER(10)   REFERENCES sales_reps(rep_id),
    activity_type VARCHAR2(30) CHECK (activity_type IN ('Call','Email','Demo','Meeting','Proposal Sent','Follow-Up')),
    activity_date DATE         NOT NULL,
    notes         VARCHAR2(500),
    outcome       VARCHAR2(20) CHECK (outcome IN ('Positive','Neutral','Negative','No Response'))
);

-- ── STEP 3: Sequences ────────────────────────────────────────

CREATE SEQUENCE seq_customer   START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_order      START WITH 1001 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_item       START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_activity   START WITH 1 INCREMENT BY 1 NOCACHE;

-- ── STEP 4: Seed Reference Data ─────────────────────────────

INSERT INTO regions VALUES (1, 'Northeast',   'USA');
INSERT INTO regions VALUES (2, 'Southeast',   'USA');
INSERT INTO regions VALUES (3, 'Midwest',     'USA');
INSERT INTO regions VALUES (4, 'Southwest',   'USA');
INSERT INTO regions VALUES (5, 'West Coast',  'USA');
INSERT INTO regions VALUES (6, 'Canada',      'Canada');
INSERT INTO regions VALUES (7, 'Europe',      'UK');
INSERT INTO regions VALUES (8, 'APAC',        'Singapore');

-- Sales reps mapped to emp_ids 1001–1020 (matches Postgres HR data)
INSERT INTO sales_reps VALUES (1, 1001, 'Alice Smith',    1, DATE '2022-03-15', 850000,  'Y');
INSERT INTO sales_reps VALUES (2, 1002, 'Bob Johnson',    2, DATE '2021-07-01', 720000,  'Y');
INSERT INTO sales_reps VALUES (3, 1003, 'Charlie Williams',3,DATE '2023-01-10', 650000,  'Y');
INSERT INTO sales_reps VALUES (4, 1004, 'Diana Brown',    4, DATE '2020-11-22', 980000,  'Y');
INSERT INTO sales_reps VALUES (5, 1005, 'Evan Jones',     5, DATE '2022-06-05', 750000,  'Y');
INSERT INTO sales_reps VALUES (6, 1006, 'Fiona Garcia',   1, DATE '2021-02-14', 820000,  'Y');
INSERT INTO sales_reps VALUES (7, 1007, 'George Miller',  2, DATE '2023-04-01', 600000,  'Y');
INSERT INTO sales_reps VALUES (8, 1008, 'Hannah Davis',   3, DATE '2020-08-30', 1100000, 'Y');
INSERT INTO sales_reps VALUES (9, 1009, 'Ian Rodriguez',  6, DATE '2022-09-15', 900000,  'Y');
INSERT INTO sales_reps VALUES (10,1010, 'Julia Martinez', 7, DATE '2021-12-01', 950000,  'Y');

-- Products
INSERT INTO products VALUES (1,  'CRM Pro Suite',          'Software',    12000, 3000, 'Y');
INSERT INTO products VALUES (2,  'Analytics Dashboard',    'Software',     8500, 1800, 'Y');
INSERT INTO products VALUES (3,  'Data Connector Pack',    'Software',     4200,  900, 'Y');
INSERT INTO products VALUES (4,  'Enterprise License',     'License',     45000, 8000, 'Y');
INSERT INTO products VALUES (5,  'Professional Services',  'Services',     2500,  800, 'Y');
INSERT INTO products VALUES (6,  'Training Package',       'Services',     1800,  400, 'Y');
INSERT INTO products VALUES (7,  'Cloud Storage (1TB)',    'Infrastructure',3600,  600, 'Y');
INSERT INTO products VALUES (8,  'Premium Support',        'Support',      6000,  500, 'Y');
INSERT INTO products VALUES (9,  'API Access Pack',        'Software',     5500, 1200, 'Y');
INSERT INTO products VALUES (10, 'Custom Integration',     'Services',    15000, 4000, 'Y');

COMMIT;

-- ── STEP 5: Generate ~10,000 rows via PL/SQL ─────────────────

DECLARE
    v_cust_id     NUMBER := 0;
    v_order_id    NUMBER := 1001;
    v_item_id     NUMBER := 0;
    v_act_id      NUMBER := 0;

    v_statuses    SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('Won','Won','Won','Lost','Negotiation','Proposal','Prospecting');
    v_segments    SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('Enterprise','Mid-Market','SMB','Startup');
    v_cities      SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('New York','Los Angeles','Chicago','Houston','Phoenix','Philadelphia','San Antonio','San Diego','Dallas','San Jose','Austin','Jacksonville','Denver','Seattle','Nashville');
    v_companies   SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('Acme Corp','GlobalTech','SkyNet Ltd','PeakSoft','Vertex Systems','BlueCrest','Novaline','Ironclad Inc','Meridian Group','Sunstone LLC','Apex Digital','CoreLogic','Brightwave','Cascade Partners','Nexus Corp');
    v_act_types   SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('Call','Email','Demo','Meeting','Proposal Sent','Follow-Up');
    v_outcomes    SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('Positive','Positive','Neutral','Negative','No Response');

    v_status      VARCHAR2(20);
    v_deal_val    NUMBER;
    v_order_date  DATE;
    v_close_date  DATE;
    v_rep_id      NUMBER;
    v_region_id   NUMBER;
    v_seg_idx     NUMBER;
    v_city        VARCHAR2(80);
    v_company     VARCHAR2(150);
    v_num_items   NUMBER;
    v_num_acts    NUMBER;
    v_product_id  NUMBER;
    v_qty         NUMBER;
    v_price       NUMBER;
    v_disc        NUMBER;
    v_line_total  NUMBER;

BEGIN
    -- Generate 500 customers
    FOR c IN 1..500 LOOP
        v_cust_id   := c;
        v_seg_idx   := MOD(c, 4) + 1;
        v_city      := v_cities(MOD(c, 15) + 1);
        v_company   := v_companies(MOD(c, 15) + 1) || ' #' || TO_CHAR(c);

        INSERT INTO customers VALUES (
            v_cust_id,
            v_company,
            'Contact ' || TO_CHAR(c),
            'contact' || TO_CHAR(c) || '@' || LOWER(REPLACE(v_company,' ','')) || '.com',
            '555-' || LPAD(TO_CHAR(MOD(c*17, 9000) + 1000), 4, '0'),
            v_city,
            CASE MOD(c,5) WHEN 0 THEN 'CA' WHEN 1 THEN 'NY' WHEN 2 THEN 'TX' WHEN 3 THEN 'FL' ELSE 'IL' END,
            'USA',
            v_segments(v_seg_idx),
            DATE '2022-01-01' + MOD(c * 7, 730)
        );
    END LOOP;
    COMMIT;

    -- Generate ~800 orders (with 10–15 items + 3–8 activities each → ~10k+ total rows)
    FOR o IN 1..800 LOOP
        v_rep_id    := MOD(o, 10) + 1;
        v_region_id := MOD(o, 8) + 1;
        v_status    := v_statuses(MOD(o, 7) + 1);
        v_order_date := DATE '2023-01-01' + MOD(o * 11, 730);

        v_close_date := CASE
            WHEN v_status IN ('Won','Lost') THEN v_order_date + MOD(o * 3, 90) + 14
            ELSE NULL
        END;

        v_deal_val := CASE v_status
            WHEN 'Enterprise' THEN (MOD(o * 13, 80) + 20) * 1000
            ELSE (MOD(o * 7, 50) + 5) * 1000
        END;
        v_deal_val := (MOD(o * 13, 900) + 100) * 100;   -- range $10k–$100k

        INSERT INTO orders VALUES (
            v_order_id,
            MOD(o, 500) + 1,
            v_rep_id,
            v_order_date,
            v_close_date,
            v_status,
            v_deal_val,
            v_region_id
        );

        -- 8–15 line items per order → ~8,800 rows in order_items
        v_num_items := MOD(o, 8) + 8;
        FOR i IN 1..v_num_items LOOP
            v_product_id := MOD(v_item_id, 10) + 1;
            v_qty        := MOD(i * 3, 10) + 1;
            v_price      := ROUND((MOD(v_item_id * 17, 10000) + 1000) / 100.0, 2) * 100;
            v_disc       := CASE WHEN MOD(v_item_id, 5) = 0 THEN 10 WHEN MOD(v_item_id, 3) = 0 THEN 5 ELSE 0 END;
            v_line_total := ROUND(v_qty * v_price * (1 - v_disc/100), 2);

            v_item_id := v_item_id + 1;
            INSERT INTO order_items VALUES (
                v_item_id,
                v_order_id,
                v_product_id,
                v_qty,
                v_price,
                v_disc,
                v_line_total
            );
        END LOOP;

        -- 3–8 CRM activities per order → ~4,400 rows in activities
        v_num_acts := MOD(o, 6) + 3;
        FOR a IN 1..v_num_acts LOOP
            v_act_id := v_act_id + 1;
            INSERT INTO activities VALUES (
                v_act_id,
                v_order_id,
                v_rep_id,
                v_act_types(MOD(v_act_id, 6) + 1),
                v_order_date + MOD(a * 5, 30),
                'Activity note for order ' || TO_CHAR(v_order_id) || ', touchpoint ' || TO_CHAR(a),
                v_outcomes(MOD(v_act_id, 5) + 1)
            );
        END LOOP;

        v_order_id := v_order_id + 1;
    END LOOP;
    COMMIT;

    DBMS_OUTPUT.PUT_LINE('Done! Rows inserted:');
    DBMS_OUTPUT.PUT_LINE('  Customers  : 500');
    DBMS_OUTPUT.PUT_LINE('  Sales Reps : 10');
    DBMS_OUTPUT.PUT_LINE('  Products   : 10');
    DBMS_OUTPUT.PUT_LINE('  Orders     : 800');
    DBMS_OUTPUT.PUT_LINE('  Order Items: ~8,800');
    DBMS_OUTPUT.PUT_LINE('  Activities : ~4,400');
    DBMS_OUTPUT.PUT_LINE('  TOTAL      : ~14,520 rows');
END;
/

-- ── STEP 6: Performance Indexes ─────────────────────────────

CREATE INDEX idx_orders_rep      ON orders(rep_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status   ON orders(status);
CREATE INDEX idx_orders_date     ON orders(order_date);
CREATE INDEX idx_items_order     ON order_items(order_id);
CREATE INDEX idx_items_product   ON order_items(product_id);
CREATE INDEX idx_acts_order      ON activities(order_id);
CREATE INDEX idx_acts_rep        ON activities(rep_id);
CREATE INDEX idx_reps_emp        ON sales_reps(emp_id);

-- ── STEP 7: Verify Row Counts ────────────────────────────────

SELECT 'regions'     AS table_name, COUNT(*) AS rows FROM regions     UNION ALL
SELECT 'sales_reps',                COUNT(*)          FROM sales_reps  UNION ALL
SELECT 'customers',                 COUNT(*)          FROM customers   UNION ALL
SELECT 'products',                  COUNT(*)          FROM products    UNION ALL
SELECT 'orders',                    COUNT(*)          FROM orders      UNION ALL
SELECT 'order_items',               COUNT(*)          FROM order_items UNION ALL
SELECT 'activities',                COUNT(*)          FROM activities;

-- ── STEP 8: Quick Sanity Queries ────────────────────────────

-- Top reps by revenue
SELECT r.rep_name, SUM(o.deal_value) AS total_revenue,
       COUNT(o.order_id) AS total_orders
FROM sales_reps r
JOIN orders o ON r.rep_id = o.rep_id
WHERE o.status = 'Won'
GROUP BY r.rep_name
ORDER BY total_revenue DESC
FETCH FIRST 5 ROWS ONLY;

-- Revenue by region
SELECT rg.region_name, SUM(o.deal_value) AS revenue
FROM regions rg
JOIN orders o ON rg.region_id = o.region_id
WHERE o.status = 'Won'
GROUP BY rg.region_name
ORDER BY revenue DESC;
