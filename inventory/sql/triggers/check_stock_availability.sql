-- ============================================================================
-- Trigger: Check Stock Availability for Storefront Transfers
-- Purpose: Prevent storefront allocations that exceed available warehouse stock
--
-- CALCULATION METHOD (preserves single source of truth):
-- - stock_product.quantity = Recorded batch size (NEVER modified by adjustments)
-- - available_quantity = recorded_quantity + SUM(approved_adjustments.quantity)
-- - Adjustments are negative for losses, positive for gains
-- ============================================================================

CREATE OR REPLACE FUNCTION check_stock_transfer_availability()
RETURNS TRIGGER AS $$
DECLARE
    v_stock_product_id UUID;
    v_recorded_quantity INTEGER;
    v_approved_adjustments INTEGER;
    v_available_quantity INTEGER;
    v_already_allocated INTEGER;
    v_remaining_available INTEGER;
    v_product_name VARCHAR(255);
    v_warehouse_name VARCHAR(255);
BEGIN
    -- Get stock product ID from the transfer
    v_stock_product_id := NEW.stock_product_id;
    
    -- Get recorded quantity (base quantity from receiving - SINGLE SOURCE OF TRUTH)
    SELECT sp.quantity, p.name, w.name
    INTO v_recorded_quantity, v_product_name, v_warehouse_name
    FROM stock_products sp
    JOIN products p ON p.id = sp.product_id
    JOIN stock s ON s.id = sp.stock_id
    JOIN warehouses w ON w.id = s.warehouse_id
    WHERE sp.id = v_stock_product_id;
    
    -- Get sum of approved/completed adjustments (negative for losses, positive for gains)
    -- This is added to recorded quantity to get available quantity
    SELECT COALESCE(SUM(quantity), 0)
    INTO v_approved_adjustments
    FROM stock_adjustments
    WHERE stock_product_id = v_stock_product_id
    AND status IN ('APPROVED', 'COMPLETED');
    
    -- Calculate available quantity (recorded + adjustments)
    -- Example: Recorded=100, Damage=-10, Found=+5 => Available=95
    v_available_quantity := v_recorded_quantity + v_approved_adjustments;
    
    -- Calculate already allocated to other storefronts
    -- For UPDATE, exclude the current record's old quantity
    IF TG_OP = 'UPDATE' THEN
        SELECT COALESCE(SUM(quantity), 0)
        INTO v_already_allocated
        FROM storefront_inventory
        WHERE stock_product_id = v_stock_product_id
        AND id != NEW.id;
    ELSE
        SELECT COALESCE(SUM(quantity), 0)
        INTO v_already_allocated
        FROM storefront_inventory
        WHERE stock_product_id = v_stock_product_id;
    END IF;
    
    -- Calculate remaining available
    v_remaining_available := v_available_quantity - v_already_allocated;
    
    -- Prevent over-allocation
    IF NEW.quantity > v_remaining_available THEN
        RAISE EXCEPTION 
            'Stock Availability Error: Insufficient stock available for transfer. Product: "%" at warehouse "%". Recorded Batch Size: %, Approved Adjustments: %, Available: %, Already Allocated: %, Remaining: %, Requested: %',
            v_product_name,
            v_warehouse_name,
            v_recorded_quantity,
            v_approved_adjustments,
            v_available_quantity,
            v_already_allocated,
            v_remaining_available,
            NEW.quantity
        USING ERRCODE = '23514', -- check_violation
              HINT = 'Reduce requested quantity or wait for pending adjustments to be approved';
    END IF;
    
    -- Ensure available quantity is not negative (data integrity check)
    IF v_available_quantity < 0 THEN
        RAISE EXCEPTION
            'Data Integrity Error: Available quantity is negative. Product: "%", Recorded: %, Adjustments: %, Available: %',
            v_product_name,
            v_recorded_quantity,
            v_approved_adjustments,
            v_available_quantity
        USING ERRCODE = '23514',
              HINT = 'Review stock adjustments for this product - total losses exceed recorded quantity';
    END IF;
    
    -- Log successful allocation
    RAISE NOTICE 
        'Stock Transfer Validated: Product "%" - Recorded: %, Adjustments: %, Available: %, Allocated: %, Remaining after transfer: %',
        v_product_name,
        v_recorded_quantity,
        v_approved_adjustments,
        v_available_quantity,
        NEW.quantity,
        v_remaining_available - NEW.quantity;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS ensure_stock_availability ON storefront_inventory;

CREATE TRIGGER ensure_stock_availability
    BEFORE INSERT OR UPDATE ON storefront_inventory
    FOR EACH ROW
    EXECUTE FUNCTION check_stock_transfer_availability();

-- Add comment for documentation
COMMENT ON FUNCTION check_stock_transfer_availability() IS 
'Validates storefront transfers using calculated available quantity (recorded + adjustments) while preserving stock_product.quantity as single source of truth';

COMMENT ON TRIGGER ensure_stock_availability ON storefront_inventory IS
'Prevents storefront transfers exceeding available stock. Uses: available = recorded_quantity + SUM(approved_adjustments)';
