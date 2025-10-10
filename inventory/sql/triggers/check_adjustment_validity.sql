-- ============================================================================
-- Trigger: Validate Stock Adjustment Before Save
-- Purpose: Prevent adjustments that would reduce stock below allocated quantity
-- ============================================================================

CREATE OR REPLACE FUNCTION check_adjustment_validity()
RETURNS TRIGGER AS $$
DECLARE
    v_current_qty INTEGER;
    v_allocated_qty INTEGER;
    v_other_adjustments INTEGER;
    v_new_available INTEGER;
    v_product_name VARCHAR(255);
BEGIN
    -- Only validate when status is APPROVED or COMPLETED
    IF NEW.status NOT IN ('APPROVED', 'COMPLETED') THEN
        RETURN NEW;
    END IF;
    
    -- Only validate negative adjustments (losses)
    IF NEW.quantity >= 0 THEN
        RETURN NEW;
    END IF;
    
    -- Get current quantity and product name for error messages
    SELECT sp.quantity, p.name
    INTO v_current_qty, v_product_name
    FROM stock_products sp
    JOIN products p ON p.id = sp.product_id
    WHERE sp.id = NEW.stock_product_id;
    
    -- Get total allocated to storefronts
    SELECT COALESCE(SUM(quantity), 0)
    INTO v_allocated_qty
    FROM storefront_inventory
    WHERE stock_product_id = NEW.stock_product_id;
    
    -- Get sum of other approved/completed adjustments
    SELECT COALESCE(SUM(quantity), 0)
    INTO v_other_adjustments
    FROM stock_adjustments
    WHERE stock_product_id = NEW.stock_product_id
    AND id != COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid)
    AND status IN ('APPROVED', 'COMPLETED');
    
    -- Calculate what available would be with this adjustment
    v_new_available := v_current_qty + v_other_adjustments + NEW.quantity;
    
    -- Ensure we don't go below allocated quantity
    IF v_new_available < v_allocated_qty THEN
        RAISE EXCEPTION 
            'Stock Integrity Violation: Adjustment would reduce stock below allocated quantity. Product: "%", Current Qty: %, Allocated to Stores: %, Other Adjustments: %, This Adjustment: %, Resulting Available: %, Required: %',
            v_product_name,
            v_current_qty,
            v_allocated_qty,
            v_other_adjustments,
            NEW.quantity,
            v_new_available,
            v_allocated_qty
        USING ERRCODE = '23514'; -- check_violation
    END IF;
    
    -- Ensure adjustment doesn't make quantity negative
    IF v_new_available < 0 THEN
        RAISE EXCEPTION
            'Stock Integrity Violation: Adjustment would make quantity negative. Product: "%", Current Qty: %, Adjustment: %, Resulting: %',
            v_product_name,
            v_current_qty,
            NEW.quantity,
            v_new_available
        USING ERRCODE = '23514';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS validate_adjustment_before_save ON stock_adjustments;

CREATE TRIGGER validate_adjustment_before_save
    BEFORE INSERT OR UPDATE ON stock_adjustments
    FOR EACH ROW
    EXECUTE FUNCTION check_adjustment_validity();

-- Add comment for documentation
COMMENT ON FUNCTION check_adjustment_validity() IS 
'Validates that stock adjustments do not violate data integrity by reducing available stock below allocated quantity';

COMMENT ON TRIGGER validate_adjustment_before_save ON stock_adjustments IS
'Prevents creation or approval of adjustments that would cause stock integrity violations';
