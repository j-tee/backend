-- SQL Script to Delete All AI Credit Records
-- Database: pos_db (PostgreSQL)
-- Date: November 7, 2025
--
-- WARNING: This will permanently delete all AI credit related data!
-- Make sure you have a backup before running this.
--
-- Usage:
--   psql -U postgres -d pos_db -f delete_ai_credits.sql
--   or run the commands below in pgAdmin or your SQL client

BEGIN;

-- Show counts before deletion
SELECT 'BEFORE DELETION - Record counts:' AS status;
SELECT 'BusinessAICredits' AS table_name, COUNT(*) AS count FROM business_ai_credits
UNION ALL
SELECT 'AITransaction' AS table_name, COUNT(*) AS count FROM ai_transactions
UNION ALL
SELECT 'AICreditPurchase' AS table_name, COUNT(*) AS count FROM ai_credit_purchases
UNION ALL
SELECT 'AIUsageAlert' AS table_name, COUNT(*) AS count FROM ai_usage_alerts;

-- Delete records (in order to avoid foreign key constraints)
DELETE FROM ai_usage_alerts;
DELETE FROM ai_transactions;
DELETE FROM ai_credit_purchases;
DELETE FROM business_ai_credits;

-- Show results
SELECT 'AFTER DELETION - All AI credit records deleted!' AS status;

-- Verify deletion
SELECT 'VERIFICATION - Record counts:' AS status;
SELECT 'BusinessAICredits' AS table_name, COUNT(*) AS count FROM business_ai_credits
UNION ALL
SELECT 'AITransaction' AS table_name, COUNT(*) AS count FROM ai_transactions
UNION ALL
SELECT 'AICreditPurchase' AS table_name, COUNT(*) AS count FROM ai_credit_purchases
UNION ALL
SELECT 'AIUsageAlert' AS table_name, COUNT(*) AS count FROM ai_usage_alerts;

COMMIT;

-- If you want to rollback instead of committing, use:
-- ROLLBACK;
