-- ============================================================================
-- Audit Log Table Creation
-- Purpose: Track all inventory quantity changes for compliance and debugging
-- ============================================================================

-- Create audit log table if it doesn't exist
CREATE TABLE IF NOT EXISTS inventory_audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by UUID,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata TEXT,
    
    -- Constraints
    CONSTRAINT valid_table_name CHECK (table_name IN ('stock_products', 'storefront_inventory', 'stock_adjustments'))
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_audit_log_record 
    ON inventory_audit_log(table_name, record_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_date 
    ON inventory_audit_log(changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_action 
    ON inventory_audit_log(action);

CREATE INDEX IF NOT EXISTS idx_audit_log_user 
    ON inventory_audit_log(changed_by) 
    WHERE changed_by IS NOT NULL;

-- Add comments for documentation
COMMENT ON TABLE inventory_audit_log IS 
'Comprehensive audit trail for all inventory quantity changes including adjustments, transfers, and sales';

COMMENT ON COLUMN inventory_audit_log.table_name IS 
'Name of the table that was modified (stock_products, storefront_inventory, stock_adjustments)';

COMMENT ON COLUMN inventory_audit_log.record_id IS 
'UUID of the record that was modified';

COMMENT ON COLUMN inventory_audit_log.action IS 
'Type of action performed (ADJUSTMENT_APPLIED, TRANSFER_CREATED, QUANTITY_UPDATED, etc.)';

COMMENT ON COLUMN inventory_audit_log.old_value IS 
'Previous value before the change (typically the old quantity)';

COMMENT ON COLUMN inventory_audit_log.new_value IS 
'New value after the change (typically the new quantity)';

COMMENT ON COLUMN inventory_audit_log.changed_by IS 
'UUID of the user who performed the action (NULL for system actions)';

COMMENT ON COLUMN inventory_audit_log.metadata IS 
'Additional context as JSON string (e.g., adjustment details, transfer info)';

-- Create function to query audit trail for a specific stock product
CREATE OR REPLACE FUNCTION get_stock_audit_trail(p_stock_product_id UUID)
RETURNS TABLE (
    log_id BIGINT,
    action VARCHAR,
    old_quantity INTEGER,
    new_quantity INTEGER,
    changed_by_email VARCHAR,
    changed_at TIMESTAMP,
    details TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ial.id,
        ial.action,
        ial.old_value::INTEGER,
        ial.new_value::INTEGER,
        u.email,
        ial.changed_at,
        ial.metadata
    FROM inventory_audit_log ial
    LEFT JOIN users u ON u.id = ial.changed_by
    WHERE ial.table_name = 'stock_products'
    AND ial.record_id = p_stock_product_id
    ORDER BY ial.changed_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_stock_audit_trail(UUID) IS 
'Retrieves complete audit trail for a specific stock product, showing all quantity changes over time';

-- Example usage:
-- SELECT * FROM get_stock_audit_trail('some-stock-product-uuid');
