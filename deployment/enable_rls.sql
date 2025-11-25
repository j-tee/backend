-- Row-Level Security (RLS) Implementation for POS Backend
-- This SQL script implements database-level multi-tenant isolation
-- Run this after deploying the application

-- ============================================================================
-- 1. ENABLE RLS ON CRITICAL TABLES
-- ============================================================================

-- Products table
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- Sales table
ALTER TABLE sales ENABLE ROW LEVEL SECURITY;

-- Customers table  
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;

-- Stock table
ALTER TABLE stock ENABLE ROW LEVEL SECURITY;

-- Suppliers table
ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;

-- AI Transactions table
ALTER TABLE ai_transactions ENABLE ROW LEVEL SECURITY;

-- Subscription tables
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_payments ENABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 2. CREATE RLS POLICIES
-- ============================================================================

-- Policy: Products - Users can only see products from their businesses
CREATE POLICY business_isolation_products ON products
    FOR ALL
    TO authenticated_users
    USING (
        business_id IN (
            SELECT business_id 
            FROM accounts_businessmembership 
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
            AND is_active = true
        )
    );

-- Policy: Sales - Users can only see sales from their businesses
CREATE POLICY business_isolation_sales ON sales
    FOR ALL
    TO authenticated_users
    USING (
        business_id IN (
            SELECT business_id 
            FROM accounts_businessmembership 
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
            AND is_active = true
        )
    );

-- Policy: Customers - Users can only see customers from their businesses
CREATE POLICY business_isolation_customers ON customers
    FOR ALL
    TO authenticated_users
    USING (
        business_id IN (
            SELECT business_id 
            FROM accounts_businessmembership 
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
            AND is_active = true
        )
    );

-- Policy: Stock - Users can only see stock from their businesses
CREATE POLICY business_isolation_stock ON stock
    FOR ALL
    TO authenticated_users
    USING (
        business_id IN (
            SELECT business_id 
            FROM accounts_businessmembership 
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
            AND is_active = true
        )
    );

-- Policy: Suppliers - Users can only see suppliers from their businesses
CREATE POLICY business_isolation_suppliers ON suppliers
    FOR ALL
    TO authenticated_users
    USING (
        business_id IN (
            SELECT business_id 
            FROM accounts_businessmembership 
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
            AND is_active = true
        )
    );

-- Policy: AI Transactions - Users can only see AI transactions from their businesses
CREATE POLICY business_isolation_ai_transactions ON ai_transactions
    FOR ALL
    TO authenticated_users
    USING (
        business_id IN (
            SELECT business_id 
            FROM accounts_businessmembership 
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
            AND is_active = true
        )
    );

-- Policy: Subscriptions - Users can only see subscriptions for their businesses
CREATE POLICY business_isolation_subscriptions ON subscriptions
    FOR ALL
    TO authenticated_users
    USING (
        business_id IN (
            SELECT business_id 
            FROM accounts_businessmembership 
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
            AND is_active = true
        )
    );

-- Policy: Subscription Payments - Users can only see payments for their subscriptions
CREATE POLICY business_isolation_subscription_payments ON subscription_payments
    FOR ALL
    TO authenticated_users
    USING (
        subscription_id IN (
            SELECT id FROM subscriptions
            WHERE business_id IN (
                SELECT business_id 
                FROM accounts_businessmembership 
                WHERE user_id = current_setting('app.current_user_id', true)::uuid
                AND is_active = true
            )
        )
    );


-- ============================================================================
-- 3. SUPERUSER BYPASS (For admin operations)
-- ============================================================================

-- Allow superusers to bypass RLS for administrative tasks
ALTER TABLE products FORCE ROW LEVEL SECURITY;
ALTER TABLE sales FORCE ROW LEVEL SECURITY;
ALTER TABLE customers FORCE ROW LEVEL SECURITY;
ALTER TABLE stock FORCE ROW LEVEL SECURITY;
ALTER TABLE suppliers FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_transactions FORCE ROW LEVEL SECURITY;
ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;
ALTER TABLE subscription_payments FORCE ROW LEVEL SECURITY;

-- Create superuser bypass policies
CREATE POLICY superuser_bypass_products ON products
    FOR ALL
    TO authenticated_users
    USING (
        current_setting('app.is_superuser', true)::boolean = true
    );

CREATE POLICY superuser_bypass_sales ON sales
    FOR ALL
    TO authenticated_users
    USING (
        current_setting('app.is_superuser', true)::boolean = true
    );

-- Repeat for other tables...


-- ============================================================================
-- 4. PERFORMANCE INDEXES
-- ============================================================================

-- Add indexes to speed up RLS queries
CREATE INDEX IF NOT EXISTS idx_business_membership_user_active 
ON accounts_businessmembership(user_id, is_active) 
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_products_business 
ON products(business_id);

CREATE INDEX IF NOT EXISTS idx_sales_business 
ON sales(business_id);

CREATE INDEX IF NOT EXISTS idx_customers_business 
ON customers(business_id);


-- ============================================================================
-- 5. VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is enabled
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename IN ('products', 'sales', 'customers', 'stock', 'suppliers')
AND schemaname = 'public';

-- List all policies
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE tablename IN ('products', 'sales', 'customers', 'stock', 'suppliers')
ORDER BY tablename, policyname;


-- ============================================================================
-- ROLLBACK SCRIPT (Use in case of issues)
-- ============================================================================

-- To disable RLS (emergency use only):
-- ALTER TABLE products DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE sales DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE customers DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE stock DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE suppliers DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE ai_transactions DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE subscription_payments DISABLE ROW LEVEL SECURITY;

-- To drop all policies:
-- DROP POLICY IF EXISTS business_isolation_products ON products;
-- DROP POLICY IF EXISTS business_isolation_sales ON sales;
-- ... etc
