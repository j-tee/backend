# 🐛 Critical Bug: Stock Adjustments Not Applied

**Date:** October 6, 2025  
**Severity:** 🔴 **CRITICAL**  
**Impact:** Approved adjustments not updating stock levels

---

## Problem Summary

### The Issue

You have created **4 stock adjustments**, but the stock level remains at **44** even though **2 adjustments are APPROVED**.

```
Product: 10mm Armoured Cable 50m (SKU: ELEC-0007)
Current Stock: 44 items

Adjustments:
1. Damage (-4)           APPROVED   ← Should reduce stock!
2. Lost/Missing (-6)     APPROVED   ← Should reduce stock!
3. Sample Use (-5)       PENDING
4. Damage (-3)           PENDING

Expected Stock: 44 - 4 - 6 = 34 items
Actual Stock: 44 items
DISCREPANCY: Stock not being updated!
```

---

## Root Cause

### Two-Step Approval Process

The system has a **two-step workflow**:

1. **PENDING** → **APPROVED** (approval step)
2. **APPROVED** → **COMPLETED** (stock update step)

**The bug:** Stock is only updated when status = **COMPLETED**, but your adjustments are stuck at **APPROVED**.

### Why This Happens

Looking at the code:

```python
# In adjustment_views.py approve() method:
def approve(self, request, pk=None):
    adjustment.approve(request.user)
    
    # Try to complete it immediately if it doesn't require further approval
    if not adjustment.requires_approval:  # ← THIS IS THE ISSUE!
        adjustment.complete()
```

**Problem:** Your adjustments have `requires_approval=True`, so they are NOT auto-completed after approval!

---

## The Confusion

### What Each Status Means

| Status | Meaning | Stock Updated? |
|--------|---------|----------------|
| PENDING | Awaiting approval | ❌ No |
| APPROVED | Manager approved it | ❌ No - waiting for completion |
| COMPLETED | Stock adjustment applied | ✅ YES |
| REJECTED | Adjustment cancelled | ❌ No |

### Current State

```
Adjustment #1 (Damage -4):
  Status: APPROVED ✅
  Stock Updated: ❌ NO
  Stock still: 44 (should be 40)

Adjustment #2 (Lost -6):
  Status: APPROVED ✅
  Stock Updated: ❌ NO
  Stock still: 44 (should be 34 after #1 and #2)
```

---

## Impact on `quantity_before`

### Why All Show 44

```
Adjustment #1 created 10:16:
  quantity_before: 44 ✅ CORRECT
  Status: APPROVED (not completed)
  Stock remains: 44

Adjustment #2 created 11:30:
  quantity_before: 44 ⚠️ LOOKS WRONG but is CORRECT
  Reason: Adjustment #1 wasn't completed yet!
  Stock was still: 44 when #2 was created

Adjustment #3 created 11:33:
  quantity_before: 44 ⚠️ LOOKS WRONG but is CORRECT
  Reason: Neither #1 nor #2 were completed!
  Stock was still: 44

Adjustment #4 created 11:34:
  quantity_before: 44 ⚠️ LOOKS WRONG but is CORRECT
  Reason: No adjustments completed yet!
  Stock was still: 44
```

**The system is working correctly!** The issue is that approvals don't automatically complete.

---

## Solution

### Option 1: Complete the APPROVED Adjustments

You need to **COMPLETE** them (not just approve):

```bash
# API calls needed:
POST /api/stock-adjustments/{id}/complete/

# For each APPROVED adjustment
```

**After completing adjustment #1:**
- Stock: 44 → 40 ✅
- Adjustment #1 status: COMPLETED

**After completing adjustment #2:**
- Stock: 40 → 34 ✅
- Adjustment #2 status: COMPLETED

### Option 2: Auto-Complete After Approval (Recommended Fix)

**Change the workflow** so APPROVED adjustments auto-complete:

```python
# In adjustment_views.py
def approve(self, request, pk=None):
    adjustment.approve(request.user)
    
    # Always complete after approval
    adjustment.complete()  # ← Remove the if condition
    
    serializer = self.get_serializer(adjustment)
    return Response(serializer.data)
```

### Option 3: Frontend Fix

**Update frontend** to call `/complete/` after `/approve/`:

```typescript
// After approving
await api.post(`/stock-adjustments/${id}/approve/`)

// Immediately complete it
await api.post(`/stock-adjustments/${id}/complete/`)
```

---

## Testing the Fix

### Step 1: Complete Existing APPROVED Adjustments

```python
from inventory.stock_adjustments import StockAdjustment

# Get approved adjustments
approved = StockAdjustment.objects.filter(status='APPROVED')

for adj in approved.order_by('created_at'):
    print(f'Completing {adj.id}: {adj.quantity:+d}')
    adj.complete()
    print(f'Stock now: {adj.stock_product.quantity}')
```

### Step 2: Verify Stock Levels

```
Before:
  Stock: 44

After completing #1 (-4):
  Stock: 40 ✅

After completing #2 (-6):
  Stock: 34 ✅

Then approve & complete #3 (-5):
  Stock: 29 ✅

Then approve & complete #4 (-3):
  Stock: 26 ✅
```

---

## Recommended Fix (Code Change)

### File: `inventory/adjustment_views.py`

**Current Code (Line 108-123):**
```python
def approve(self, request, pk=None):
    """Approve a pending adjustment"""
    adjustment = self.get_object()
    
    if adjustment.status != 'PENDING':
        return Response(
            {'error': f'Cannot approve adjustment with status: {adjustment.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        adjustment.approve(request.user)
        
        # Try to complete it immediately if it doesn't require further approval
        if not adjustment.requires_approval:  # ← PROBLEM: Never true after approval!
            adjustment.complete()
        
        serializer = self.get_serializer(adjustment)
        return Response(serializer.data)
```

**Recommended Fix:**
```python
def approve(self, request, pk=None):
    """Approve a pending adjustment"""
    adjustment = self.get_object()
    
    if adjustment.status != 'PENDING':
        return Response(
            {'error': f'Cannot approve adjustment with status: {adjustment.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        adjustment.approve(request.user)
        
        # Auto-complete after approval (apply to stock immediately)
        adjustment.complete()  # ← FIXED: Always complete after approval
        
        serializer = self.get_serializer(adjustment)
        return Response(serializer.data)
```

---

## Why This Bug Exists

### Design Intent (Probably)

The two-step process was likely designed for:
1. **Manager approval** - "Yes, this adjustment is valid"
2. **System completion** - "Now apply it to inventory"

This might be useful for:
- Scheduling adjustments for later
- Batch processing
- Additional verification steps

### Reality

In practice:
- Users expect approval = applied
- Having APPROVED but not COMPLETED is confusing
- Stock levels don't match expectations
- Creates the exact issue you're experiencing

---

## Immediate Action Required

### For Your Current Data

Run this to complete the approved adjustments:

```python
python manage.py shell

from inventory.stock_adjustments import StockAdjustment

# Complete all APPROVED adjustments in order
approved = StockAdjustment.objects.filter(
    status='APPROVED'
).order_by('created_at')

for adj in approved:
    sp = adj.stock_product
    print(f'Before: {sp.quantity}')
    adj.complete()
    sp.refresh_from_db()
    print(f'After: {sp.quantity} ({adj.quantity:+d})')
    print('---')
```

---

## Summary

| Aspect | Finding |
|--------|---------|
| **Bug** | APPROVED adjustments not updating stock |
| **Root Cause** | Two-step process: APPROVED ≠ COMPLETED |
| **Impact** | Stock levels incorrect, calculations confusing |
| **Fix** | Auto-complete after approval OR complete manually |
| **Status** | 2 adjustments stuck at APPROVED |

**Next Step:** Choose Option 1 (manual complete) or Option 2 (code fix) to resolve.

---

**Status:** 🔴 **CRITICAL - REQUIRES IMMEDIATE ACTION**  
**Resolution:** Apply one of the 3 solutions above  
**Prevention:** Update approval workflow to auto-complete
