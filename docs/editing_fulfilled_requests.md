# Editing Fulfilled Stock Requests - Documentation

**Last Updated:** October 3, 2025  
**Status:** ✅ Implemented and Tested

---

## Overview

Managers and owners can directly edit fulfilled stock request quantities when errors are discovered or adjustments are needed. This provides a simple, straightforward way to correct stock request records without complex workflows.

## Use Case Example

**Scenario:** A storefront staff member requested 20 electric cables, but after fulfillment, the manager realizes only 10 are actually needed.

**Solution:** The manager directly edits the fulfilled request, reducing the quantity from 20 to 10. The system automatically recalculates totals, and all subsequent inventory computations use the updated value.

---

## How It Works

### Principle

Storefront inventory is a **calculated value** based on the sum of all fulfilled request quantities for each product:

```
Storefront Total = SUM(fulfilled_request_quantities)
```

When a manager edits a fulfilled request:
1. The `requested_quantity` on line items is updated
2. The request remains in `FULFILLED` status
3. All inventory calculations automatically use the new quantities
4. No inventory adjustments are triggered

### Example Calculation

**Initial State:**
- Request #1: 20 cables (FULFILLED)
- Request #2: 15 cables (FULFILLED)
- **Storefront total: 35 cables**

**After Manager Edits Request #1 from 20 → 10:**
- Request #1: 10 cables (FULFILLED)
- Request #2: 15 cables (FULFILLED)
- **Storefront total: 25 cables** (automatically recalculated)

---

## API Usage

### Endpoint

```
PATCH /inventory/api/transfer-requests/{id}/
```

### Permissions

- **Managers, Admins, Owners**: Can edit any request in any status
- **Staff**: Can only edit their own requests when status is `NEW`

### Request Payload

```json
{
  "notes": "Adjusted quantities - over-requested initially",
  "line_items": [
    {
      "id": "line-item-uuid",
      "product": "product-uuid",
      "requested_quantity": 10,
      "notes": "Reduced from 20 to 10"
    }
  ]
}
```

### Response

```json
{
  "id": "request-uuid",
  "status": "FULFILLED",
  "storefront": "storefront-uuid",
  "storefront_name": "Downtown Store",
  "priority": "MEDIUM",
  "notes": "Adjusted quantities - over-requested initially",
  "line_items": [
    {
      "id": "line-item-uuid",
      "product": "product-uuid",
      "product_name": "Electric Cable 10mm",
      "sku": "CABLE-10MM",
      "requested_quantity": 10,
      "unit_of_measure": "pcs",
      "notes": "Reduced from 20 to 10"
    }
  ],
  "created_at": "2025-10-03T08:00:00Z",
  "updated_at": "2025-10-03T14:30:00Z"
}
```

---

## Frontend Integration

### TypeScript Interface

```typescript
interface EditFulfilledRequestPayload {
  notes?: string
  line_items: Array<{
    id: UUID
    product: UUID
    requested_quantity: number
    notes?: string
  }>
}
```

### API Service Method

```typescript
export async function editFulfilledRequest(
  requestId: UUID,
  payload: EditFulfilledRequestPayload
): Promise<TransferRequest> {
  const response = await apiClient.patch(
    `/inventory/api/transfer-requests/${requestId}/`,
    payload
  )
  return response.data
}
```

### React Component Example

```typescript
const EditFulfilledRequestForm: React.FC<{ request: TransferRequest }> = ({ request }) => {
  const [lineItems, setLineItems] = useState(request.line_items)
  const [notes, setNotes] = useState(request.notes || '')
  const [editRequest, { isLoading }] = useEditFulfilledRequestMutation()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      await editRequest({
        requestId: request.id,
        payload: {
          notes,
          line_items: lineItems.map(item => ({
            id: item.id,
            product: item.product,
            requested_quantity: item.requested_quantity,
            notes: item.notes
          }))
        }
      }).unwrap()
      
      toast.success('Request updated successfully')
    } catch (error) {
      toast.error('Failed to update request')
    }
  }

  const handleQuantityChange = (lineItemId: UUID, newQuantity: number) => {
    setLineItems(prev => prev.map(item =>
      item.id === lineItemId
        ? { ...item, requested_quantity: newQuantity }
        : item
    ))
  }

  return (
    <form onSubmit={handleSubmit}>
      <h3>Edit Fulfilled Request</h3>
      <p className="text-sm text-yellow-600">
        ⚠️ This request has already been fulfilled. Editing will update inventory calculations.
      </p>

      {lineItems.map((item) => (
        <div key={item.id} className="border p-4 mb-2">
          <label className="block mb-2">
            {item.product_name} ({item.sku})
          </label>
          <input
            type="number"
            min="1"
            value={item.requested_quantity}
            onChange={(e) => handleQuantityChange(item.id, parseInt(e.target.value))}
            className="border rounded px-3 py-2"
          />
          <input
            type="text"
            placeholder="Adjustment reason"
            value={item.notes || ''}
            onChange={(e) => setLineItems(prev => prev.map(i =>
              i.id === item.id ? { ...i, notes: e.target.value } : i
            ))}
            className="border rounded px-3 py-2 ml-2"
          />
        </div>
      ))}

      <textarea
        placeholder="Overall adjustment notes..."
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="w-full border rounded px-3 py-2 mb-4"
      />

      <button 
        type="submit" 
        disabled={isLoading}
        className="bg-blue-600 text-white px-4 py-2 rounded"
      >
        {isLoading ? 'Updating...' : 'Update Request'}
      </button>
    </form>
  )
}
```

---

## Audit Trail

### Tracking Changes

To track who made changes and why:

1. **Use the `notes` field** on the request to document overall reason
2. **Use the `notes` field** on individual line items for specific adjustments
3. **Check `updated_at` timestamp** to see when the last change was made
4. **Compare with `created_at`** to identify edited requests

### Example Notes

```
Request notes: "Adjusted quantities after inventory recount"

Line item notes:
- "Reduced from 20 to 10 - over-requested"
- "Increased from 5 to 8 - additional need identified"
```

---

## Business Rules

### When to Use This Feature

✅ **Appropriate scenarios:**
- Correcting data entry errors
- Adjusting for over/under-requests
- Updating after physical inventory verification
- Reconciling discrepancies

❌ **Not appropriate for:**
- Returning items to warehouse (use separate transfer)
- Cancelling requests (use cancel endpoint)
- Initial request creation (use POST endpoint)

### Best Practices

1. **Always add notes** explaining why the adjustment was made
2. **Verify inventory** before making adjustments
3. **Communicate changes** to relevant staff members
4. **Document in line item notes** for item-specific reasons
5. **Use manager permissions** - don't delegate this to staff

---

## Validation Rules

1. **Quantity must be positive:** `requested_quantity > 0`
2. **Product must belong to business:** Validated in serializer
3. **Manager permissions required:** For FULFILLED requests
4. **Request must exist:** Returns 404 if not found

---

## Error Handling

### Common Errors

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Permission denied | 403 | Staff trying to edit | Use manager account |
| Invalid quantity | 400 | Quantity ≤ 0 | Use positive number |
| Request not found | 404 | Invalid ID | Verify request ID |
| Product mismatch | 400 | Product not in business | Use correct product |

### Example Error Response

```json
{
  "line_items": {
    "0": "Requested quantity must be greater than zero."
  }
}
```

---

## Testing

### Manual Test Script

The implementation includes a test script at `test_fulfilled_edit.py`:

```bash
python test_fulfilled_edit.py
```

This demonstrates:
1. Creating a fulfilled request
2. Editing quantities as a manager
3. Verifying the request remains FULFILLED
4. Confirming calculations use updated quantities

### Unit Tests

All existing tests pass (8/8):
```bash
python manage.py test inventory.tests.TransferRequestWorkflowAPITest
```

---

## Comparison: Simple Edit vs. Complex Returns

### ❌ Complex Returns Workflow (NOT IMPLEMENTED)

- Parent-child request linking
- Bidirectional transfers (FORWARD/REVERSE)
- Returnable quantity calculations
- Return validation against fulfilled quantities
- Separate return endpoints
- Complex data model with 6+ new fields

### ✅ Simple Edit (IMPLEMENTED)

- Direct quantity editing
- Single PATCH endpoint
- No new database fields
- No new migrations
- Automatic inventory recalculation
- Simple and error-free

---

## Migration from Returns Concept

If you previously considered implementing a Returns workflow, here's why this is better:

| Aspect | Complex Returns | Simple Edit |
|--------|----------------|-------------|
| **Complexity** | High (6+ new fields) | Low (uses existing) |
| **Error prone** | Yes (quantity limits) | No (direct update) |
| **API endpoints** | 3+ new endpoints | 1 existing endpoint |
| **Database changes** | New migration | No changes |
| **Frontend effort** | Significant | Minimal |
| **User experience** | Confusing | Intuitive |
| **Maintenance** | High | Low |

---

## Role Permissions Summary

| Role | Create | Edit NEW (own) | Edit FULFILLED | Cancel |
|------|--------|----------------|----------------|--------|
| STAFF | ✅ | ✅ | ❌ | ✅ (own, NEW) |
| MANAGER | ✅ | ✅ | ✅ | ✅ |
| ADMIN | ✅ | ✅ | ✅ | ✅ |
| OWNER | ✅ | ✅ | ✅ | ✅ |

---

## Frequently Asked Questions

**Q: Will editing a fulfilled request trigger inventory adjustments?**  
A: No. The inventory is recalculated based on the new quantities, but no automatic adjustments are made. If you need to physically move items, create a new transfer.

**Q: Can I edit a cancelled request?**  
A: Yes, managers can edit requests in any status, including CANCELLED, though this is not recommended.

**Q: What happens to linked transfers?**  
A: The `linked_transfer_reference` remains unchanged. The edit only affects the request record, not the transfer.

**Q: Can I add or remove line items from fulfilled requests?**  
A: Yes, managers can add/remove line items by including `_destroy: true` for items to delete, or omitting existing item IDs to add new ones.

**Q: How do I track who made edits?**  
A: Check the `updated_at` timestamp and encourage managers to add notes explaining their changes.

---

**Implementation Status:** ✅ Complete  
**Tests Passing:** 8/8  
**Migration Required:** None  
**Breaking Changes:** None

