# Frontend Implementation Guide - Stock Adjustment View & Edit

**Date:** 2025-10-09  
**Feature:** View and Edit Stock Adjustments  
**Backend Endpoints:** `/inventory/api/stock-adjustments/`

---

## Overview

This guide covers the implementation of viewing and editing stock adjustments. Users can:
- View details of any stock adjustment
- Edit adjustments that are in **PENDING** status only
- Receive clear error messages when trying to edit non-pending adjustments

## API Endpoints

### 1. List Stock Adjustments
```
GET /inventory/api/stock-adjustments/
```

**Query Parameters:**
- `status` - Filter by status (PENDING, APPROVED, COMPLETED)
- `adjustment_type` - Filter by type (DAMAGE, THEFT, FOUND, CORRECTION, etc.)
- `page` - Page number for pagination
- `page_size` - Items per page

**Response:**
```typescript
{
  count: number;
  next: string | null;
  previous: string | null;
  results: StockAdjustment[];
}
```

### 2. Get Adjustment Detail
```
GET /inventory/api/stock-adjustments/{id}/
```

**Response:** See `StockAdjustment` interface below

### 3. Create New Adjustment
```
POST /inventory/api/stock-adjustments/
```

**Request Body:**
```typescript
{
  stock_product: string;           // UUID of stock product
  adjustment_type: string;         // DAMAGE | THEFT | FOUND | CORRECTION | etc.
  quantity: number;                // Negative for losses, positive for gains
  reason: string;
  unit_cost?: number;             // Optional, defaults to stock product cost
  reference_number?: string;      // Optional reference
}
```

### 4. Update Adjustment (Full)
```
PUT /inventory/api/stock-adjustments/{id}/
```

**⚠️ IMPORTANT:** Only works for adjustments with `status: "PENDING"`

**Request Body:**
```typescript
{
  stock_product: string;
  adjustment_type: string;
  quantity: number;
  reason: string;
  unit_cost?: number;
  reference_number?: string;
}
```

**Success Response (200):** Updated `StockAdjustment` object

**Error Response (400):**
```typescript
{
  error: "Cannot edit adjustment with status: APPROVED. Only PENDING adjustments can be edited."
}
```

### 5. Update Adjustment (Partial)
```
PATCH /inventory/api/stock-adjustments/{id}/
```

**⚠️ IMPORTANT:** Only works for adjustments with `status: "PENDING"`

**Request Body (any subset of fields):**
```typescript
{
  reason?: string;                // Update just the reason
  quantity?: number;              // Update just the quantity
  adjustment_type?: string;       // Update just the type
  // ... any other fields
}
```

**Success Response (200):** Updated `StockAdjustment` object

**Error Response (400):** Same as PUT

### 6. Approve Adjustment
```
POST /inventory/api/stock-adjustments/{id}/approve/
```

Changes status from PENDING → APPROVED

### 7. Reject Adjustment
```
POST /inventory/api/stock-adjustments/{id}/reject/
```

Changes status from PENDING → REJECTED

### 8. Complete Adjustment
```
POST /inventory/api/stock-adjustments/{id}/complete/
```

Changes status from APPROVED → COMPLETED (applies to inventory)

---

## TypeScript Interfaces

```typescript
interface StockAdjustment {
  id: string;
  business: string;
  stock_product: string;
  stock_product_details: {
    id: string;
    product_name: string;
    product_code: string;
    quantity_at_creation: number | null;
    current_quantity: number;
    warehouse: string;
    supplier: string;
    unit_cost: string;
    retail_price: string;
  };
  adjustment_type: AdjustmentType;
  adjustment_type_display: string;
  quantity: number;
  unit_cost: string;
  total_cost: string;
  reason: string;
  reference_number: string | null;
  status: AdjustmentStatus;
  status_display: string;
  requires_approval: boolean;
  created_by: string;
  created_by_name: string;
  approved_by: string | null;
  approved_by_name: string | null;
  created_at: string;              // ISO 8601 datetime
  approved_at: string | null;      // ISO 8601 datetime
  completed_at: string | null;     // ISO 8601 datetime
  has_photos: boolean;
  has_documents: boolean;
  related_sale: string | null;
  related_transfer: string | null;
  financial_impact: string;        // Decimal string
  is_increase: boolean;
  is_decrease: boolean;
  photos: Photo[];
  documents: Document[];
}

type AdjustmentStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'COMPLETED';

type AdjustmentType = 
  | 'DAMAGE'       // Damage/Breakage
  | 'THEFT'        // Theft/Shrinkage
  | 'EXPIRY'       // Expired/Obsolete
  | 'FOUND'        // Found Inventory
  | 'CORRECTION'   // Inventory Correction
  | 'RETURN'       // Customer Return
  | 'TRANSFER_OUT' // Transfer Out
  | 'TRANSFER_IN'  // Transfer In
  | 'OTHER';       // Other

interface Photo {
  id: string;
  url: string;
  thumbnail_url: string;
  uploaded_at: string;
}

interface Document {
  id: string;
  file_name: string;
  file_url: string;
  file_type: string;
  uploaded_at: string;
}
```

---

## React Component Examples

### 1. View Adjustment Detail Modal

```tsx
import { useState, useEffect } from 'react';
import { Modal, Badge, Alert } from '@/components/ui';

interface AdjustmentDetailModalProps {
  adjustmentId: string;
  isOpen: boolean;
  onClose: () => void;
  onEdit?: (adjustment: StockAdjustment) => void;
}

export function AdjustmentDetailModal({
  adjustmentId,
  isOpen,
  onClose,
  onEdit
}: AdjustmentDetailModalProps) {
  const [adjustment, setAdjustment] = useState<StockAdjustment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !adjustmentId) return;

    const fetchAdjustment = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `/inventory/api/stock-adjustments/${adjustmentId}/`,
          {
            headers: {
              'Authorization': `Bearer ${getAuthToken()}`,
              'Content-Type': 'application/json',
            }
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch adjustment details');
        }

        const data = await response.json();
        setAdjustment(data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchAdjustment();
  }, [adjustmentId, isOpen]);

  if (!isOpen) return null;

  const canEdit = adjustment?.status === 'PENDING';

  return (
    <Modal open={isOpen} onClose={onClose} maxWidth="lg">
      <Modal.Header>
        <h2>Stock Adjustment Details</h2>
        <Badge variant={getStatusVariant(adjustment?.status)}>
          {adjustment?.status_display}
        </Badge>
      </Modal.Header>

      <Modal.Body>
        {loading && <Spinner />}
        
        {error && (
          <Alert variant="error">{error}</Alert>
        )}

        {adjustment && (
          <div className="space-y-4">
            {/* Product Information */}
            <Section title="Product Information">
              <InfoRow label="Product Name" value={adjustment.stock_product_details.product_name} />
              <InfoRow label="Product Code" value={adjustment.stock_product_details.product_code} />
              <InfoRow label="Warehouse" value={adjustment.stock_product_details.warehouse} />
              <InfoRow label="Supplier" value={adjustment.stock_product_details.supplier} />
            </Section>

            {/* Adjustment Details */}
            <Section title="Adjustment Details">
              <InfoRow label="Type" value={adjustment.adjustment_type_display} />
              <InfoRow 
                label="Quantity" 
                value={
                  <Badge variant={adjustment.is_decrease ? 'danger' : 'success'}>
                    {adjustment.quantity > 0 ? '+' : ''}{adjustment.quantity}
                  </Badge>
                }
              />
              <InfoRow label="Unit Cost" value={`$${adjustment.unit_cost}`} />
              <InfoRow 
                label="Financial Impact" 
                value={
                  <span className={adjustment.is_decrease ? 'text-red-600' : 'text-green-600'}>
                    {adjustment.is_decrease ? '-' : '+'}${Math.abs(parseFloat(adjustment.financial_impact))}
                  </span>
                }
              />
              <InfoRow label="Reason" value={adjustment.reason} />
              {adjustment.reference_number && (
                <InfoRow label="Reference #" value={adjustment.reference_number} />
              )}
            </Section>

            {/* Audit Information */}
            <Section title="Audit Trail">
              <InfoRow label="Created By" value={adjustment.created_by_name} />
              <InfoRow label="Created At" value={formatDateTime(adjustment.created_at)} />
              {adjustment.approved_by_name && (
                <>
                  <InfoRow label="Approved By" value={adjustment.approved_by_name} />
                  <InfoRow label="Approved At" value={formatDateTime(adjustment.approved_at!)} />
                </>
              )}
              {adjustment.completed_at && (
                <InfoRow label="Completed At" value={formatDateTime(adjustment.completed_at)} />
              )}
            </Section>

            {/* Photos and Documents */}
            {(adjustment.has_photos || adjustment.has_documents) && (
              <Section title="Attachments">
                {adjustment.photos.length > 0 && (
                  <PhotoGrid photos={adjustment.photos} />
                )}
                {adjustment.documents.length > 0 && (
                  <DocumentList documents={adjustment.documents} />
                )}
              </Section>
            )}
          </div>
        )}
      </Modal.Body>

      <Modal.Footer>
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
        {canEdit && onEdit && (
          <Button variant="primary" onClick={() => onEdit(adjustment!)}>
            Edit Adjustment
          </Button>
        )}
      </Modal.Footer>
    </Modal>
  );
}

// Helper function
function getStatusVariant(status?: AdjustmentStatus) {
  switch (status) {
    case 'PENDING': return 'warning';
    case 'APPROVED': return 'info';
    case 'COMPLETED': return 'success';
    case 'REJECTED': return 'danger';
    default: return 'default';
  }
}
```

### 2. Edit Adjustment Form

```tsx
import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Modal, Button, Alert, Input, Select, TextArea } from '@/components/ui';

interface EditAdjustmentFormProps {
  adjustment: StockAdjustment;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updated: StockAdjustment) => void;
}

interface AdjustmentFormData {
  adjustment_type: AdjustmentType;
  quantity: number;
  reason: string;
  unit_cost?: string;
  reference_number?: string;
}

export function EditAdjustmentForm({
  adjustment,
  isOpen,
  onClose,
  onSuccess
}: EditAdjustmentFormProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, reset, formState: { errors, isDirty } } = useForm<AdjustmentFormData>({
    defaultValues: {
      adjustment_type: adjustment.adjustment_type,
      quantity: adjustment.quantity,
      reason: adjustment.reason,
      unit_cost: adjustment.unit_cost,
      reference_number: adjustment.reference_number || '',
    }
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        adjustment_type: adjustment.adjustment_type,
        quantity: adjustment.quantity,
        reason: adjustment.reason,
        unit_cost: adjustment.unit_cost,
        reference_number: adjustment.reference_number || '',
      });
      setError(null);
    }
  }, [adjustment, isOpen, reset]);

  const onSubmit = async (data: AdjustmentFormData) => {
    try {
      setSubmitting(true);
      setError(null);

      const response = await fetch(
        `/inventory/api/stock-adjustments/${adjustment.id}/`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            stock_product: adjustment.stock_product,
            adjustment_type: data.adjustment_type,
            quantity: Number(data.quantity),
            reason: data.reason,
            unit_cost: data.unit_cost ? parseFloat(data.unit_cost) : undefined,
            reference_number: data.reference_number || undefined,
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to update adjustment');
      }

      const updated = await response.json();
      onSuccess(updated);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Partial update for just the reason field (example)
  const updateReasonOnly = async (newReason: string) => {
    try {
      setSubmitting(true);
      const response = await fetch(
        `/inventory/api/stock-adjustments/${adjustment.id}/`,
        {
          method: 'PATCH',
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason: newReason })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to update');
      }

      const updated = await response.json();
      onSuccess(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  // Show warning if trying to edit non-pending adjustment
  if (adjustment.status !== 'PENDING') {
    return (
      <Modal open={isOpen} onClose={onClose}>
        <Modal.Header>
          <h2>Cannot Edit Adjustment</h2>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="warning">
            This adjustment has status <strong>{adjustment.status_display}</strong> and cannot be edited.
            Only adjustments in <strong>PENDING</strong> status can be modified.
          </Alert>
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose}>Close</Button>
        </Modal.Footer>
      </Modal>
    );
  }

  return (
    <Modal open={isOpen} onClose={onClose} maxWidth="md">
      <form onSubmit={handleSubmit(onSubmit)}>
        <Modal.Header>
          <h2>Edit Stock Adjustment</h2>
          <Badge variant="warning">PENDING</Badge>
        </Modal.Header>

        <Modal.Body>
          {error && (
            <Alert variant="error" className="mb-4">
              {error}
            </Alert>
          )}

          <div className="space-y-4">
            {/* Product Info (Read-only) */}
            <Alert variant="info">
              <strong>Product:</strong> {adjustment.stock_product_details.product_name}
              {' '}({adjustment.stock_product_details.product_code})
              <br />
              <strong>Current Quantity:</strong> {adjustment.stock_product_details.current_quantity}
            </Alert>

            {/* Adjustment Type */}
            <Select
              label="Adjustment Type"
              {...register('adjustment_type', { required: 'Type is required' })}
              error={errors.adjustment_type?.message}
            >
              <option value="DAMAGE">Damage/Breakage</option>
              <option value="THEFT">Theft/Shrinkage</option>
              <option value="EXPIRY">Expired/Obsolete</option>
              <option value="FOUND">Found Inventory</option>
              <option value="CORRECTION">Inventory Correction</option>
              <option value="RETURN">Customer Return</option>
              <option value="OTHER">Other</option>
            </Select>

            {/* Quantity */}
            <Input
              type="number"
              label="Quantity"
              placeholder="Negative for losses, positive for gains"
              {...register('quantity', { 
                required: 'Quantity is required',
                valueAsNumber: true,
                validate: value => value !== 0 || 'Quantity cannot be zero'
              })}
              error={errors.quantity?.message}
              helpText="Use negative numbers for losses (e.g., -5), positive for gains (e.g., +3)"
            />

            {/* Unit Cost */}
            <Input
              type="number"
              step="0.01"
              label="Unit Cost"
              placeholder={adjustment.stock_product_details.unit_cost}
              {...register('unit_cost')}
              error={errors.unit_cost?.message}
              helpText="Optional - defaults to stock product cost"
            />

            {/* Reason */}
            <TextArea
              label="Reason"
              rows={4}
              {...register('reason', { 
                required: 'Reason is required',
                minLength: { value: 10, message: 'Reason must be at least 10 characters' }
              })}
              error={errors.reason?.message}
              placeholder="Explain why this adjustment is needed..."
            />

            {/* Reference Number */}
            <Input
              type="text"
              label="Reference Number (Optional)"
              placeholder="e.g., INV-2025-001"
              {...register('reference_number')}
              error={errors.reference_number?.message}
            />
          </div>
        </Modal.Body>

        <Modal.Footer>
          <Button 
            type="button" 
            variant="outline" 
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            variant="primary"
            disabled={!isDirty || submitting}
            loading={submitting}
          >
            {submitting ? 'Saving...' : 'Save Changes'}
          </Button>
        </Modal.Footer>
      </form>
    </Modal>
  );
}
```

### 3. List View with Edit Action

```tsx
import { useState } from 'react';
import { Table, Badge, Button, DropdownMenu } from '@/components/ui';

export function StockAdjustmentsList() {
  const [selectedAdjustment, setSelectedAdjustment] = useState<StockAdjustment | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);

  const handleEdit = (adjustment: StockAdjustment) => {
    if (adjustment.status !== 'PENDING') {
      toast.error('Only pending adjustments can be edited');
      return;
    }
    setSelectedAdjustment(adjustment);
    setShowEditModal(true);
  };

  const handleView = (adjustment: StockAdjustment) => {
    setSelectedAdjustment(adjustment);
    setShowDetailModal(true);
  };

  return (
    <>
      <Table>
        <Table.Header>
          <Table.Row>
            <Table.Head>Product</Table.Head>
            <Table.Head>Type</Table.Head>
            <Table.Head>Quantity</Table.Head>
            <Table.Head>Status</Table.Head>
            <Table.Head>Created</Table.Head>
            <Table.Head>Actions</Table.Head>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {adjustments.map(adjustment => (
            <Table.Row key={adjustment.id}>
              <Table.Cell>
                <div>
                  <div className="font-medium">
                    {adjustment.stock_product_details.product_name}
                  </div>
                  <div className="text-sm text-gray-500">
                    {adjustment.stock_product_details.product_code}
                  </div>
                </div>
              </Table.Cell>
              <Table.Cell>{adjustment.adjustment_type_display}</Table.Cell>
              <Table.Cell>
                <Badge variant={adjustment.is_decrease ? 'danger' : 'success'}>
                  {adjustment.quantity > 0 ? '+' : ''}{adjustment.quantity}
                </Badge>
              </Table.Cell>
              <Table.Cell>
                <Badge variant={getStatusVariant(adjustment.status)}>
                  {adjustment.status_display}
                </Badge>
              </Table.Cell>
              <Table.Cell>{formatDate(adjustment.created_at)}</Table.Cell>
              <Table.Cell>
                <DropdownMenu>
                  <DropdownMenu.Item onClick={() => handleView(adjustment)}>
                    View Details
                  </DropdownMenu.Item>
                  <DropdownMenu.Item 
                    onClick={() => handleEdit(adjustment)}
                    disabled={adjustment.status !== 'PENDING'}
                  >
                    Edit
                  </DropdownMenu.Item>
                  {adjustment.status === 'PENDING' && (
                    <>
                      <DropdownMenu.Divider />
                      <DropdownMenu.Item onClick={() => handleApprove(adjustment)}>
                        Approve
                      </DropdownMenu.Item>
                      <DropdownMenu.Item 
                        onClick={() => handleReject(adjustment)}
                        variant="danger"
                      >
                        Reject
                      </DropdownMenu.Item>
                    </>
                  )}
                </DropdownMenu>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table>

      {/* Modals */}
      {selectedAdjustment && (
        <>
          <AdjustmentDetailModal
            adjustmentId={selectedAdjustment.id}
            isOpen={showDetailModal}
            onClose={() => setShowDetailModal(false)}
            onEdit={handleEdit}
          />
          <EditAdjustmentForm
            adjustment={selectedAdjustment}
            isOpen={showEditModal}
            onClose={() => setShowEditModal(false)}
            onSuccess={handleUpdateSuccess}
          />
        </>
      )}
    </>
  );
}
```

---

## Key Implementation Rules

### ✅ DO

1. **Check status before showing edit button**
   ```tsx
   const canEdit = adjustment.status === 'PENDING';
   ```

2. **Handle 400 errors gracefully**
   ```tsx
   if (response.status === 400) {
     const error = await response.json();
     showToast(error.error, 'error'); // Show the backend error message
   }
   ```

3. **Use PATCH for partial updates**
   ```tsx
   // Only updating reason
   await fetch(url, {
     method: 'PATCH',
     body: JSON.stringify({ reason: newReason })
   });
   ```

4. **Show clear status indicators**
   ```tsx
   <Badge variant={adjustment.status === 'PENDING' ? 'warning' : 'default'}>
     {adjustment.status_display}
   </Badge>
   ```

5. **Refresh data after successful edit**
   ```tsx
   const onSuccess = (updated: StockAdjustment) => {
     setAdjustment(updated);
     refetchList();
     toast.success('Adjustment updated successfully');
   };
   ```

### ❌ DON'T

1. **Don't allow editing non-pending adjustments**
   ```tsx
   // BAD - no status check
   <Button onClick={() => editAdjustment(item)}>Edit</Button>

   // GOOD - conditional rendering
   {adjustment.status === 'PENDING' && (
     <Button onClick={() => editAdjustment(item)}>Edit</Button>
   )}
   ```

2. **Don't calculate total_cost on frontend**
   ```tsx
   // BAD
   const totalCost = quantity * unitCost;

   // GOOD - backend calculates and returns it
   const totalCost = adjustment.total_cost;
   ```

3. **Don't ignore backend error messages**
   ```tsx
   // BAD
   catch (err) {
     toast.error('Failed to update');
   }

   // GOOD
   catch (err) {
     const message = err.response?.data?.error || err.message;
     toast.error(message);
   }
   ```

4. **Don't send unnecessary fields**
   ```tsx
   // BAD - sending read-only fields
   body: JSON.stringify({
     ...adjustment,  // Includes id, created_at, etc.
     reason: newReason
   })

   // GOOD - only editable fields
   body: JSON.stringify({
     stock_product: adjustment.stock_product,
     adjustment_type: data.adjustment_type,
     quantity: data.quantity,
     reason: data.reason
   })
   ```

---

## Status Flow Chart

```
┌─────────┐
│ PENDING │ ←── Initial state (can EDIT)
└────┬────┘
     │
     ├──→ approve() ──→ ┌──────────┐
     │                  │ APPROVED │ (cannot edit)
     │                  └────┬─────┘
     │                       │
     │                       └──→ complete() ──→ ┌───────────┐
     │                                            │ COMPLETED │ (cannot edit)
     │                                            └───────────┘
     │
     └──→ reject() ──→ ┌──────────┐
                       │ REJECTED │ (cannot edit)
                       └──────────┘
```

**Key Rules:**
- Only **PENDING** adjustments can be edited
- Once approved, rejected, or completed → **locked forever**
- Backend enforces this rule and returns 400 error if violated

---

## Error Handling Examples

```tsx
// Example 1: Handle edit attempt on non-pending adjustment
async function updateAdjustment(id: string, data: Partial<AdjustmentFormData>) {
  try {
    const response = await fetch(`/inventory/api/stock-adjustments/${id}/`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data)
    });

    if (response.status === 400) {
      const error = await response.json();
      // Backend returns: { error: "Cannot edit adjustment with status: APPROVED..." }
      toast.error(error.error);
      return null;
    }

    if (!response.ok) {
      throw new Error('Network error');
    }

    return await response.json();
  } catch (err) {
    console.error('Failed to update adjustment:', err);
    toast.error('Failed to update adjustment. Please try again.');
    return null;
  }
}

// Example 2: Preemptive check before showing edit UI
function canEditAdjustment(adjustment: StockAdjustment): boolean {
  return adjustment.status === 'PENDING';
}

// Usage
{canEditAdjustment(adjustment) ? (
  <Button onClick={handleEdit}>Edit</Button>
) : (
  <Tooltip content={`Cannot edit ${adjustment.status_display} adjustments`}>
    <Button disabled>Edit</Button>
  </Tooltip>
)}
```

---

## Testing Checklist

- [ ] **View Detail:** Can view any adjustment regardless of status
- [ ] **Edit Button:** Only shown for PENDING adjustments
- [ ] **PUT Request:** Full update works for PENDING adjustments
- [ ] **PATCH Request:** Partial update works for PENDING adjustments
- [ ] **Error on APPROVED:** Attempting to edit APPROVED returns clear error
- [ ] **Error on COMPLETED:** Attempting to edit COMPLETED returns clear error
- [ ] **Error on REJECTED:** Attempting to edit REJECTED returns clear error
- [ ] **Validation:** Form validates required fields (quantity, reason)
- [ ] **Recalculation:** Backend recalculates `total_cost` after edit
- [ ] **Success Feedback:** Shows success message and refreshes data
- [ ] **Error Messages:** Displays backend error messages to user
- [ ] **Optimistic UI:** Optional - update UI before server confirms

---

## Common Use Cases

### Use Case 1: Quick Reason Update
User wants to update just the reason text without changing anything else.

```tsx
async function quickUpdateReason(adjustmentId: string, newReason: string) {
  const response = await fetch(
    `/inventory/api/stock-adjustments/${adjustmentId}/`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: newReason })
    }
  );
  
  if (response.ok) {
    return await response.json();
  }
  
  throw new Error('Failed to update reason');
}
```

### Use Case 2: Change Quantity and Type
User realizes they marked 5 units as "damage" but it should be 8 units of "theft".

```tsx
async function updateQuantityAndType(
  adjustmentId: string,
  quantity: number,
  adjustmentType: AdjustmentType
) {
  const response = await fetch(
    `/inventory/api/stock-adjustments/${adjustmentId}/`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        quantity,
        adjustment_type: adjustmentType
      })
    }
  );
  
  if (response.ok) {
    const updated = await response.json();
    // Backend automatically recalculates total_cost
    console.log('New total cost:', updated.total_cost);
    return updated;
  }
  
  throw new Error('Failed to update adjustment');
}
```

### Use Case 3: Prevent Edit After Approval
User tries to edit but adjustment was just approved by manager.

```tsx
function AdjustmentEditButton({ adjustment }: { adjustment: StockAdjustment }) {
  const [isEditing, setIsEditing] = useState(false);

  const handleEdit = () => {
    // Double-check status before opening modal
    if (adjustment.status !== 'PENDING') {
      toast.error(
        `This adjustment is ${adjustment.status_display} and can no longer be edited.`
      );
      return;
    }
    setIsEditing(true);
  };

  return (
    <>
      <Button
        onClick={handleEdit}
        disabled={adjustment.status !== 'PENDING'}
      >
        Edit
      </Button>
      {isEditing && (
        <EditAdjustmentForm
          adjustment={adjustment}
          isOpen={isEditing}
          onClose={() => setIsEditing(false)}
          onSuccess={handleSuccess}
        />
      )}
    </>
  );
}
```

---

## API Response Examples

### Successful Edit (200 OK)
```json
{
  "id": "7d806c69-fea0-45af-b1c4-8d077ba3fb5b",
  "business": "225ac09f-28ba-4222-b142-6d6ad1484ee9",
  "stock_product": "7f06fb68-52d3-4b46-90cd-b2bdc50f6e9d",
  "stock_product_details": {
    "product_name": "Test Product",
    "product_code": "TEST-001",
    "current_quantity": 100
  },
  "adjustment_type": "THEFT",
  "adjustment_type_display": "Theft/Shrinkage",
  "quantity": -8,
  "unit_cost": "10.00",
  "total_cost": "80.00",
  "reason": "Updated reason - theft instead of damage",
  "status": "PENDING",
  "status_display": "Pending Approval",
  "created_by_name": "John Doe",
  "created_at": "2025-10-09T20:22:44.260522Z",
  "financial_impact": "-80.00",
  "is_decrease": true
}
```

### Error: Editing Non-Pending (400 Bad Request)
```json
{
  "error": "Cannot edit adjustment with status: APPROVED. Only PENDING adjustments can be edited."
}
```

### Error: Editing Completed (400 Bad Request)
```json
{
  "error": "Cannot edit adjustment with status: COMPLETED. Only PENDING adjustments can be edited."
}
```

---

## Questions or Issues?

If you encounter any problems:

1. **Check the network tab** to see the actual request/response
2. **Verify the adjustment status** - only PENDING can be edited
3. **Look at the error response** - backend provides descriptive messages
4. **Test with Postman/curl** first to isolate frontend vs backend issues

### Example curl test:
```bash
# Get adjustment
curl -X GET \
  http://localhost:8000/inventory/api/stock-adjustments/{id}/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Update adjustment (PATCH)
curl -X PATCH \
  http://localhost:8000/inventory/api/stock-adjustments/{id}/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Updated reason text"}'
```

**Backend is ready!** All tests passing. The edit functionality works exactly as documented above. 🚀
