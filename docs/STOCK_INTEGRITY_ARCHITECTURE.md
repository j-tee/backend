# Stock Adjustment Architecture - Preserving Single Source of Truth

**Visual guide to the revised data integrity solution**

---

## 🏗️ Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SINGLE SOURCE OF TRUTH                        │
│                                                                  │
│              stock_products.quantity = 100                       │
│                                                                  │
│  ✓ Set when stock received from supplier                        │
│  ✓ Modified ONLY by explicit user action (CRUD, physical count) │
│  ✓ NEVER changed by adjustments, triggers, or automation        │
│  ✓ Immutable baseline for all calculations                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Referenced by
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ADJUSTMENTS (Stored Separately)               │
│                                                                  │
│  stock_adjustments:                                              │
│    - Damage: -10 units (APPROVED)                               │
│    - Theft: -5 units (APPROVED)                                 │
│    - Found: +3 units (APPROVED)                                 │
│                                                                  │
│  ✓ Stored as separate records                                   │
│  ✓ Never modify stock_products.quantity                         │
│  ✓ Summed dynamically for calculations                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Used to calculate
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              CALCULATED AVAILABLE QUANTITY (Dynamic)             │
│                                                                  │
│  Formula: recorded + SUM(approved_adjustments)                   │
│  Example: 100 + (-10 -5 +3) = 88                                │
│                                                                  │
│  ✓ Computed at read time                                        │
│  ✓ Never stored in database                                     │
│  ✓ Always reflects current reality                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Used for
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              ALLOCATION DECISIONS (Trigger-Enforced)             │
│                                                                  │
│  Transfer Request: 90 units                                      │
│  Check: 90 <= 88? ❌ REJECTED                                   │
│                                                                  │
│  ✓ Trigger calculates available dynamically                     │
│  ✓ Prevents over-allocation                                     │
│  ✓ Maintains data integrity                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow: Receiving to Reconciliation

```
STEP 1: STOCK RECEIVING
┌────────────────────────────────────┐
│ Supplier delivers 100 units        │
│ User records in system             │
└────────────────────────────────────┘
                │
                ▼
        stock_products.quantity = 100 ✓
        (Single source of truth set)


STEP 2: DAMAGE OCCURS
┌────────────────────────────────────┐
│ 10 units damaged in warehouse      │
│ Manager creates adjustment          │
└────────────────────────────────────┘
                │
                ▼
        stock_adjustments:
          - type: DAMAGE
          - quantity: -10
          - status: PENDING
        
        stock_products.quantity = 100 ✓
        (Unchanged - still single source of truth)


STEP 3: ADJUSTMENT APPROVED
┌────────────────────────────────────┐
│ Supervisor approves adjustment     │
└────────────────────────────────────┘
                │
                ▼
        stock_adjustments:
          - status: APPROVED ✓
        
        Trigger: audit_adjustment_approval()
          - Logs to audit trail ✓
          - Does NOT modify quantity ✓
        
        stock_products.quantity = 100 ✓
        (STILL unchanged - preserved!)


STEP 4: AVAILABILITY CALCULATION
┌────────────────────────────────────┐
│ System calculates available        │
└────────────────────────────────────┘
                │
                ▼
        available = quantity + SUM(adjustments)
        available = 100 + (-10)
        available = 90 ✓
        
        stock_products.quantity = 100 ✓
        (Still the original recorded value)


STEP 5: TRANSFER REQUEST
┌────────────────────────────────────┐
│ Storefront requests 95 units       │
└────────────────────────────────────┘
                │
                ▼
        Trigger: check_stock_transfer_availability()
          - Calculates: available = 100 + (-10) = 90
          - Checks: 95 <= 90? ❌
          - RAISES EXCEPTION ✓
        
        Error: "Insufficient stock available.
                Recorded: 100, Adjustments: -10,
                Available: 90, Requested: 95"
        
        stock_products.quantity = 100 ✓
        (Never touched during this check)


STEP 6: RECONCILIATION VIEW
┌────────────────────────────────────┐
│ User views stock reconciliation    │
└────────────────────────────────────┘
                │
                ▼
        Display:
          Recorded Batch Size: 100 ✓
          Adjustments: -10 ✓
          Available: 90 ✓
          Allocated to Stores: 0
          Warehouse Available: 90 ✓
        
        stock_products.quantity = 100 ✓
        (Original value preserved for reconciliation)
```

---

## 🔄 Physical Count Correction Flow

```
SCENARIO: Physical count reveals discrepancy

STEP 1: PHYSICAL COUNT
┌────────────────────────────────────┐
│ System shows: 90 available         │
│   (100 recorded - 10 damage)       │
│ Physical count: 85 actual          │
│ Discrepancy: -5 units unaccounted  │
└────────────────────────────────────┘
                │
                ▼
        Investigation needed!


STEP 2: USER DECISION
┌────────────────────────────────────┐
│ Manager investigates discrepancy   │
│ Determines: Theft (not recorded)   │
│ Decision: Update system to reality │
└────────────────────────────────────┘
                │
                ▼
        Two options:

        OPTION A: Create Adjustment Only
          - Create: THEFT adjustment -5
          - Status: APPROVED
          - Result: available = 100 + (-10 -5) = 85 ✓
          - quantity = 100 (unchanged)

        OPTION B: Update Baseline + Adjustment
          - UI: "Update recorded quantity to match physical?"
          - User confirms: YES
          - UPDATE stock_products SET quantity = 85 ✓
          - Create: CORRECTION adjustment -15 (audit trail)
          - Result: recorded = 85, adjustments = 0, available = 85 ✓


BEST PRACTICE: OPTION A (Adjustment Only)
  - Preserves original receiving record
  - Clear audit trail of what happened
  - Adjustments explain the difference
```

---

## 🔍 Database Trigger Logic

### Trigger 1: Audit Adjustment Approval
```sql
-- PURPOSE: Log approvals WITHOUT modifying quantity

FUNCTION audit_adjustment_approval():
  IF adjustment.status changed to APPROVED:
    -- Get current quantity (for logging only)
    current_qty = SELECT quantity FROM stock_products
    
    -- Log the approval
    INSERT INTO audit_log (
      action: 'ADJUSTMENT_APPROVED',
      metadata: {
        recorded_qty: current_qty,  -- For reference
        adjustment: adjustment.quantity,
        note: 'quantity unchanged (single source of truth)'
      }
    )
    
    -- DO NOT UPDATE stock_products.quantity ✓
    -- It stays as the single source of truth
  
  RETURN adjustment
```

### Trigger 2: Check Transfer Availability
```sql
-- PURPOSE: Prevent over-allocation using calculated availability

FUNCTION check_stock_transfer_availability():
  -- Get recorded quantity (baseline)
  recorded = SELECT quantity FROM stock_products
  
  -- Calculate adjustments (dynamic)
  adjustments = SELECT SUM(quantity) FROM stock_adjustments
                WHERE status IN ('APPROVED', 'COMPLETED')
  
  -- Calculate available (NOT stored anywhere)
  available = recorded + adjustments
  
  -- Get already allocated
  allocated = SELECT SUM(quantity) FROM storefront_inventory
  
  -- Calculate remaining
  remaining = available - allocated
  
  -- Enforce constraint
  IF transfer.quantity > remaining:
    RAISE EXCEPTION 'Insufficient stock available'
  
  -- Note: stock_products.quantity NEVER modified ✓
  
  RETURN transfer
```

### Trigger 3: Validate Adjustment
```sql
-- PURPOSE: Prevent adjustments that violate integrity

FUNCTION check_adjustment_validity():
  IF adjustment.status IN ('APPROVED', 'COMPLETED'):
    -- Calculate what available would be
    recorded = SELECT quantity FROM stock_products
    other_adjustments = SELECT SUM(quantity) FROM stock_adjustments
                        WHERE id != adjustment.id
    new_available = recorded + other_adjustments + adjustment.quantity
    
    -- Get allocated
    allocated = SELECT SUM(quantity) FROM storefront_inventory
    
    -- Prevent if new_available < allocated
    IF new_available < allocated:
      RAISE EXCEPTION 'Would reduce below allocated'
    
    -- Note: stock_products.quantity NEVER modified ✓
  
  RETURN adjustment
```

---

## 💾 Database Schema

```sql
-- SINGLE SOURCE OF TRUTH
CREATE TABLE stock_products (
    id UUID PRIMARY KEY,
    quantity INTEGER NOT NULL,  -- ONLY modified by user CRUD
    -- ... other fields
);

-- ADJUSTMENTS (stored separately)
CREATE TABLE stock_adjustments (
    id UUID PRIMARY KEY,
    stock_product_id UUID REFERENCES stock_products(id),
    quantity INTEGER NOT NULL,  -- Negative for losses, positive for gains
    status VARCHAR(20),         -- PENDING, APPROVED, COMPLETED
    -- ... other fields
);

-- ALLOCATIONS
CREATE TABLE storefront_inventory (
    id UUID PRIMARY KEY,
    stock_product_id UUID REFERENCES stock_products(id),
    quantity INTEGER NOT NULL,
    -- ... other fields
);

-- AUDIT TRAIL
CREATE TABLE inventory_audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100),
    record_id UUID,
    action VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    metadata TEXT,  -- JSON with additional context
    changed_at TIMESTAMP
);
```

---

## 🎨 Frontend Display

```typescript
interface StockDetails {
  // Single source of truth
  recorded_batch_size: number;        // stock_products.quantity
  
  // Calculated values
  approved_adjustments_total: number; // SUM(adjustments)
  available_quantity: number;         // recorded + adjustments
  
  // Allocations
  allocated_to_stores: number;        // SUM(transfers)
  warehouse_available: number;        // available - allocated
  
  // Breakdown
  adjustments: Array<{
    type: string;
    quantity: number;
    status: string;
    date: string;
  }>;
}

// UI Display
<Card>
  <Stat label="Recorded Batch Size" value={recorded_batch_size} />
  <Stat label="Adjustments" value={approved_adjustments_total} variant={negative ? 'danger' : 'success'} />
  <Divider />
  <Stat label="Available" value={available_quantity} variant="primary" />
  <Stat label="Allocated to Stores" value={allocated_to_stores} />
  <Stat label="Warehouse Available" value={warehouse_available} variant="success" />
</Card>
```

---

## ✅ Architecture Validation Checklist

- [ ] `stock_products.quantity` is NEVER modified by triggers ✓
- [ ] Adjustments stored in separate `stock_adjustments` table ✓
- [ ] Available calculated dynamically: `recorded + SUM(adjustments)` ✓
- [ ] Triggers enforce constraints using calculated values ✓
- [ ] Audit trail logs approvals, NOT quantity mutations ✓
- [ ] Frontend receives both recorded AND available values ✓
- [ ] Single source of truth preserved throughout system ✓

---

**This architecture ensures data integrity while maintaining clean separation of concerns.**

The key insight: **Calculate from the truth, don't mutate the truth.**
