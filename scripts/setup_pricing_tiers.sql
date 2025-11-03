-- Setup Pricing Tiers and Tax Configurations for Production
-- Run this on production database to populate missing data

-- Insert Pricing Tiers (if they don't exist)
INSERT INTO subscription_pricing_tier (id, min_storefronts, max_storefronts, base_price, price_per_additional_storefront, currency, is_active, description, created_at, updated_at)
VALUES 
    (gen_random_uuid(), 1, 1, 100.00, 0.00, 'GHS', true, 'Tier for 1 storefront', NOW(), NOW()),
    (gen_random_uuid(), 2, 2, 150.00, 0.00, 'GHS', true, 'Tier for 2 storefronts', NOW(), NOW()),
    (gen_random_uuid(), 3, 3, 180.00, 0.00, 'GHS', true, 'Tier for 3 storefronts', NOW(), NOW()),
    (gen_random_uuid(), 4, 4, 200.00, 0.00, 'GHS', true, 'Tier for 4 storefronts', NOW(), NOW()),
    (gen_random_uuid(), 5, NULL, 200.00, 50.00, 'GHS', true, 'Tier for 5+ storefronts (base + per additional)', NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Insert Tax Configurations (if they don't exist)
INSERT INTO subscriptions_taxconfiguration (id, code, name, rate, is_percentage, applies_to_subscriptions, is_active, calculation_order, effective_from, description, created_at, updated_at)
VALUES 
    (gen_random_uuid(), 'VAT_GH', 'VAT', 3.00, true, true, true, 1, '2024-01-01', 'Value Added Tax (Ghana)', NOW(), NOW()),
    (gen_random_uuid(), 'NHIL_GH', 'NHIL', 2.50, true, true, true, 2, '2024-01-01', 'National Health Insurance Levy (Ghana)', NOW(), NOW()),
    (gen_random_uuid(), 'GETFUND_GH', 'GETFund Levy', 2.50, true, true, true, 3, '2024-01-01', 'Ghana Education Trust Fund Levy', NOW(), NOW()),
    (gen_random_uuid(), 'COVID19_GH', 'COVID-19 Health Recovery Levy', 1.00, true, true, true, 4, '2024-01-01', 'COVID-19 Health Recovery Levy (Ghana)', NOW(), NOW())
ON CONFLICT (code) DO NOTHING;

-- Verify the data was inserted
SELECT 'Pricing Tiers Created:' as status, COUNT(*) as count FROM subscription_pricing_tier;
SELECT 'Tax Configurations Created:' as status, COUNT(*) as count FROM subscriptions_taxconfiguration WHERE is_active = true;
