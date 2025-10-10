-- ============================================================================
-- Trigger: Audit Stock Adjustment Approval
-- Purpose: Log adjustment approvals to audit trail WITHOUT modifying stock_product.quantity
-- 
-- IMPORTANT: This trigger does NOT modify stock_product.quantity to preserve
-- single source of truth. The quantity field should only be modified through
-- explicit user actions (receiving stock, physical count corrections).
-- 
-- Stock availability calculations should use:
-- available_qty = stock_product.quantity + SUM(approved_adjustments.quantity)
-- ============================================================================

CREATE OR REPLACE FUNCTION audit_adjustment_approval()
RETURNS TRIGGER AS $$
DECLARE
    v_product_name VARCHAR(255);
    v_current_quantity INTEGER;
BEGIN
    -- Only log when transitioning TO APPROVED or COMPLETED FROM PENDING
    IF NEW.status IN ('APPROVED', 'COMPLETED') AND OLD.status = 'PENDING' THEN
        
        -- Get current stock quantity and product name for audit
        SELECT sp.quantity, p.name
        INTO v_current_quantity, v_product_name
        FROM stock_products sp
        JOIN products p ON p.id = sp.product_id
        WHERE sp.id = NEW.stock_product_id;
        
        -- Log the adjustment approval to audit table
        -- NOTE: We do NOT modify stock_product.quantity - it remains the recorded batch size
        INSERT INTO inventory_audit_log (
            table_name,
            record_id,
            action,
            old_value,
            new_value,
            changed_by,
            changed_at,
            metadata
        ) VALUES (
            'stock_adjustments',
            NEW.id,
            'ADJUSTMENT_APPROVED',
            OLD.status::TEXT,
            NEW.status::TEXT,
            NEW.approved_by,
            NOW(),
            json_build_object(
                'adjustment_id', NEW.id,
                'stock_product_id', NEW.stock_product_id,
                'adjustment_type', NEW.adjustment_type,
                'adjustment_quantity', NEW.quantity,
                'product_name', v_product_name,
                'reason', NEW.reason,
                'recorded_batch_size', v_current_quantity,
                'note', 'Adjustment approved - stock_product.quantity unchanged (single source of truth)'
            )::TEXT
        );
        
        -- Raise notice for logging purposes
        RAISE NOTICE 
            'Stock Adjustment Approved: Product "%" - Adjustment: % units (%s), Recorded Batch Size: % (unchanged) - Adjustment ID: %',
            v_product_name,
            NEW.quantity,
            NEW.adjustment_type,
            v_current_quantity,
            NEW.id;
            
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS apply_adjustment_on_approval ON stock_adjustments;
DROP TRIGGER IF EXISTS audit_adjustment_on_approval ON stock_adjustments;

CREATE TRIGGER audit_adjustment_on_approval
    AFTER UPDATE ON stock_adjustments
    FOR EACH ROW
    WHEN (NEW.status IN ('APPROVED', 'COMPLETED') AND OLD.status = 'PENDING')
    EXECUTE FUNCTION audit_adjustment_approval();

-- Add comment for documentation
COMMENT ON FUNCTION audit_adjustment_approval() IS 
'Logs stock adjustment approvals to audit trail. Does NOT modify stock_product.quantity to preserve single source of truth. Available quantity should be calculated as: recorded_quantity + SUM(approved_adjustments)';

COMMENT ON TRIGGER audit_adjustment_on_approval ON stock_adjustments IS
'Audits adjustment approvals WITHOUT modifying stock_product.quantity - preserves single source of truth principle';
