# Customer Update Endpoint Documentation

## 🎯 Overview

The **Customer Update** endpoint allows updating the customer associated with a sale that is still in DRAFT status. This is essential for POS workflows where the customer is selected after the sale has been created.

**Endpoint**: `POST/PATCH /sales/api/sales/{sale_id}/update_customer/`

---

## ⚠️ Critical Use Case

This endpoint solves a critical POS workflow issue:

1. **Problem**: POS creates a DRAFT sale automatically when user starts adding items
2. **Issue**: Customer is often selected AFTER items are added to cart
3. **Old Behavior**: No way to update customer on existing DRAFT sale
4. **Solution**: This endpoint allows safe customer updates on DRAFT sales

---

## 🔒 Security & Validation

### 1. Status Restriction
- ✅ **Only DRAFT sales** can have customer updated
- ❌ **COMPLETED sales** cannot be modified
- ❌ **CANCELLED sales** cannot be modified

### 2. Business Boundary Protection
- ✅ Customer **must belong to same business** as the sale
- ❌ Cross-business customer assignment is **blocked**

### 3. Audit Trail
- 📝 All customer changes are **logged to AuditLog**
- Records: old customer, new customer, timestamp, user

---

## 📡 API Reference

### Request

**URL**: `/sales/api/sales/{sale_id}/update_customer/`

**Methods**: `POST`, `PATCH`

**Authentication**: Required (Token)

**Headers**:
```http
Content-Type: application/json
Authorization: Token {your-auth-token}
```

**Body**:
```json
{
  "customer": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Parameters**:
- `customer` (required, UUID): The UUID of the customer to assign to the sale

---

### Response

#### Success Response (200 OK)

```json
{
  "message": "Customer updated successfully to Fred Amugi",
  "previous_customer": "Walk-in Customer",
  "new_customer": "Fred Amugi",
  "sale": {
    "id": "sale-uuid-here",
    "customer": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "customer_name": "Fred Amugi",
    "status": "DRAFT",
    "type": "WHOLESALE",
    "total_amount": "0.00",
    "business": "business-uuid",
    "storefront": "storefront-uuid",
    // ... other sale fields
  }
}
```

#### Error Responses

**400 Bad Request - Non-DRAFT Sale**:
```json
{
  "error": "Cannot update customer on a sale that is not in DRAFT status",
  "current_status": "COMPLETED",
  "allowed_status": "DRAFT",
  "message": "Customer can only be changed before the sale is completed. To change customer on a completed sale, you must cancel and recreate it."
}
```

**400 Bad Request - Missing Customer Field**:
```json
{
  "error": "customer field is required",
  "message": "Please provide a customer UUID in the request body",
  "example": {
    "customer": "uuid-of-customer"
  }
}
```

**404 Not Found - Invalid Customer**:
```json
{
  "error": "Customer not found or does not belong to this business",
  "customer_id": "provided-uuid",
  "business_id": "sale-business-uuid",
  "message": "The customer must exist and belong to the same business as the sale"
}
```

**400 Bad Request - Invalid UUID Format**:
```json
{
  "error": "Invalid customer ID format",
  "message": "Customer ID must be a valid UUID"
}
```

---

## 💻 Frontend Integration

### Step 1: Create Sale Service Function

```typescript
// services/salesService.ts

interface UpdateCustomerParams {
  saleId: string;
  customerId: string;
}

interface UpdateCustomerResponse {
  message: string;
  previous_customer: string | null;
  new_customer: string;
  sale: Sale;
}

export const updateSaleCustomer = async (
  params: UpdateCustomerParams
): Promise<UpdateCustomerResponse> => {
  const { saleId, customerId } = params;
  
  const response = await fetch(
    `/sales/api/sales/${saleId}/update_customer/`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${getAuthToken()}`
      },
      body: JSON.stringify({
        customer: customerId
      })
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to update customer');
  }
  
  return response.json();
};
```

---

### Step 2: Implement in POS Component

```tsx
// components/POSPage.tsx

import React, { useState } from 'react';
import { updateSaleCustomer } from '../services/salesService';
import { toast } from 'react-toastify';

interface Sale {
  id: string;
  customer: string | null;
  customer_name: string | null;
  status: string;
  type: 'RETAIL' | 'WHOLESALE';
}

interface Customer {
  id: string;
  name: string;
  customer_type: string;
}

const POSPage: React.FC = () => {
  const [currentSale, setCurrentSale] = useState<Sale | null>(null);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [isUpdating, setIsUpdating] = useState(false);
  
  // Handle customer selection from dropdown
  const handleCustomerChange = async (customerId: string) => {
    if (!currentSale) {
      toast.error('No active sale');
      return;
    }
    
    if (currentSale.status !== 'DRAFT') {
      toast.error('Cannot change customer on completed sale');
      return;
    }
    
    setIsUpdating(true);
    
    try {
      const result = await updateSaleCustomer({
        saleId: currentSale.id,
        customerId: customerId
      });
      
      // Update local state
      setCurrentSale(result.sale);
      setSelectedCustomerId(customerId);
      
      // Show success message
      toast.success(result.message);
      
      console.log('Customer updated:', {
        from: result.previous_customer,
        to: result.new_customer
      });
      
    } catch (error) {
      console.error('Failed to update customer:', error);
      toast.error(error.message || 'Failed to update customer');
      
      // Revert selection on error
      setSelectedCustomerId(currentSale.customer || '');
      
    } finally {
      setIsUpdating(false);
    }
  };
  
  return (
    <div className="pos-page">
      {/* Customer Selection Dropdown */}
      <div className="customer-selector">
        <label htmlFor="customer-select">Customer:</label>
        <select
          id="customer-select"
          value={selectedCustomerId}
          onChange={(e) => handleCustomerChange(e.target.value)}
          disabled={!currentSale || currentSale.status !== 'DRAFT' || isUpdating}
        >
          <option value="">Select Customer</option>
          {customers.map(customer => (
            <option key={customer.id} value={customer.id}>
              {customer.name} ({customer.customer_type})
            </option>
          ))}
        </select>
        
        {isUpdating && <span className="spinner">⏳</span>}
      </div>
      
      {/* Current Sale Display */}
      {currentSale && (
        <div className="current-sale-info">
          <h3>Current Sale</h3>
          <p>
            <strong>Customer:</strong> {currentSale.customer_name || 'Not selected'}
          </p>
          <p>
            <strong>Type:</strong> {currentSale.type}
          </p>
          <p>
            <strong>Status:</strong> {currentSale.status}
          </p>
        </div>
      )}
      
      {/* Rest of POS UI */}
    </div>
  );
};

export default POSPage;
```

---

### Step 3: Real-Time Customer Selection

```tsx
// Advanced implementation with immediate feedback

const CustomerSelector: React.FC<{
  sale: Sale | null;
  onCustomerUpdate: (sale: Sale) => void;
}> = ({ sale, onCustomerUpdate }) => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  
  useEffect(() => {
    if (sale?.customer) {
      setSelectedId(sale.customer);
    }
  }, [sale]);
  
  const handleSelect = async (customerId: string) => {
    if (!sale || !customerId) return;
    
    // Optimistic update
    setSelectedId(customerId);
    setIsLoading(true);
    
    try {
      const result = await updateSaleCustomer({
        saleId: sale.id,
        customerId
      });
      
      onCustomerUpdate(result.sale);
      toast.success(`Customer changed to ${result.new_customer}`);
      
    } catch (error) {
      // Revert on error
      setSelectedId(sale.customer || '');
      toast.error('Failed to update customer');
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="customer-selector-widget">
      <select
        value={selectedId}
        onChange={(e) => handleSelect(e.target.value)}
        disabled={!sale || sale.status !== 'DRAFT' || isLoading}
        className="customer-dropdown"
      >
        <option value="">👤 Select Customer</option>
        {customers.map(customer => (
          <option key={customer.id} value={customer.id}>
            {customer.name}
            {customer.customer_type === 'WHOLESALE' && ' 📦'}
            {customer.customer_type === 'RETAIL' && ' 🛒'}
          </option>
        ))}
      </select>
      
      {isLoading && (
        <div className="loading-indicator">
          <span className="spinner">⏳</span>
          <span>Updating...</span>
        </div>
      )}
    </div>
  );
};
```

---

## 🔄 Complete POS Workflow

### Typical Flow

```typescript
// 1. User opens POS → Create DRAFT sale
const startSale = async () => {
  const sale = await createSale({
    storefront: storefrontId,
    type: 'RETAIL',
    status: 'DRAFT'
  });
  setCurrentSale(sale);
};

// 2. User selects customer from dropdown
const selectCustomer = async (customerId: string) => {
  const result = await updateSaleCustomer({
    saleId: currentSale.id,
    customerId
  });
  setCurrentSale(result.sale);
};

// 3. User adds items to cart
const addItem = async (productId: string, quantity: number) => {
  await addItemToSale({
    saleId: currentSale.id,
    product: productId,
    quantity
  });
};

// 4. User completes payment
const completeSale = async (paymentDetails: Payment) => {
  const completedSale = await finalizeSale({
    saleId: currentSale.id,
    ...paymentDetails
  });
  
  // Customer is now locked in
  console.log('Final customer:', completedSale.customer_name);
};

// 5. Generate receipt
const printReceipt = async () => {
  const receiptUrl = `/sales/api/sales/${currentSale.id}/receipt/?format=html`;
  window.open(receiptUrl, '_blank');
};
```

---

## 🎨 UI/UX Best Practices

### 1. Visual Feedback

```css
/* Show when customer can be changed */
.customer-selector.editable {
  border: 2px solid #10b981;
  background: #ecfdf5;
}

/* Show when customer is locked */
.customer-selector.locked {
  border: 2px solid #94a3b8;
  background: #f1f5f9;
  cursor: not-allowed;
}

/* Loading state */
.customer-selector.loading {
  opacity: 0.6;
  pointer-events: none;
}
```

### 2. Error Handling

```typescript
const handleCustomerUpdateError = (error: any) => {
  if (error.current_status === 'COMPLETED') {
    toast.error('Sale is already completed. Customer cannot be changed.');
    return;
  }
  
  if (error.error?.includes('not found')) {
    toast.error('Customer not found or does not belong to your business');
    return;
  }
  
  if (error.error?.includes('required')) {
    toast.error('Please select a customer');
    return;
  }
  
  // Generic error
  toast.error('Failed to update customer. Please try again.');
};
```

### 3. Confirmation for Changes

```typescript
const handleCustomerChange = async (newCustomerId: string) => {
  if (currentSale.customer && saleItems.length > 0) {
    // Ask for confirmation if items already in cart
    const confirmed = await showConfirmDialog({
      title: 'Change Customer?',
      message: `This sale already has items. Change customer from "${currentSale.customer_name}" to "${getCustomerName(newCustomerId)}"?`,
      confirmText: 'Change Customer',
      cancelText: 'Keep Current'
    });
    
    if (!confirmed) return;
  }
  
  await updateSaleCustomer({
    saleId: currentSale.id,
    customerId: newCustomerId
  });
};
```

---

## 📊 Audit Trail

### Viewing Customer Change History

```typescript
// Fetch audit logs for a sale
const getCustomerChangeHistory = async (saleId: string) => {
  const response = await fetch(
    `/sales/api/audit-logs/?sale=${saleId}&event_type=sale.customer_updated`,
    {
      headers: {
        'Authorization': `Token ${authToken}`
      }
    }
  );
  
  const logs = await response.json();
  
  return logs.map((log: any) => ({
    timestamp: log.timestamp,
    user: log.user_name,
    oldCustomer: log.event_data.old_customer_name,
    newCustomer: log.event_data.new_customer_name,
    description: log.description
  }));
};
```

### Audit Log Entry Example

```json
{
  "id": "audit-log-uuid",
  "event_type": "sale.customer_updated",
  "timestamp": "2025-10-11T10:30:45.123456Z",
  "user": "user-uuid",
  "user_name": "John Cashier",
  "sale": "sale-uuid",
  "event_data": {
    "old_customer_id": "walk-in-customer-uuid",
    "old_customer_name": "Walk-in Customer",
    "new_customer_id": "fred-uuid",
    "new_customer_name": "Fred Amugi",
    "sale_status": "DRAFT"
  },
  "description": "Customer updated from \"Walk-in Customer\" to \"Fred Amugi\" on sale abc123",
  "ip_address": "192.168.1.100"
}
```

---

## ✅ Testing Checklist

### Functional Tests

- [ ] Can update customer on DRAFT sale
- [ ] Cannot update customer on COMPLETED sale
- [ ] Cannot update customer on CANCELLED sale
- [ ] Customer must exist in system
- [ ] Customer must belong to same business
- [ ] Returns updated sale object
- [ ] Audit log created for change
- [ ] Previous customer stored in audit
- [ ] New customer stored in audit

### Integration Tests

- [ ] Customer selection persists through page refresh
- [ ] Customer shows on receipt after completion
- [ ] Multiple customer changes logged correctly
- [ ] Concurrent updates handled safely
- [ ] Works with wholesale/retail toggle

### UI Tests

- [ ] Dropdown disabled on completed sales
- [ ] Loading indicator shows during update
- [ ] Success message displayed
- [ ] Error messages clear and helpful
- [ ] Customer name updates in UI immediately

---

## 🐛 Troubleshooting

### Issue: "404 Not Found"

**Cause**: Endpoint URL incorrect or sale doesn't exist

**Solution**:
```typescript
// Verify URL format
const url = `/sales/api/sales/${saleId}/update_customer/`;

// Check sale exists first
const sale = await fetchSale(saleId);
if (!sale) {
  console.error('Sale not found');
}
```

### Issue: "Cannot update customer on completed sale"

**Cause**: Sale status is not DRAFT

**Solution**:
```typescript
// Check status before attempting update
if (sale.status !== 'DRAFT') {
  toast.warn('Sale is already completed');
  return;
}
```

### Issue: "Customer not found or does not belong to this business"

**Cause**: Customer ID invalid or from different business

**Solution**:
```typescript
// Fetch customers for current business only
const customers = await fetchCustomers({
  business: currentBusinessId
});

// Validate customer exists in list
const customerExists = customers.some(c => c.id === selectedId);
if (!customerExists) {
  toast.error('Invalid customer selection');
}
```

---

## 🔐 Security Considerations

1. **Authentication Required**: All requests must include valid auth token
2. **Business Isolation**: Customers from other businesses cannot be assigned
3. **Status Protection**: Only DRAFT sales can be modified
4. **Audit Logging**: All changes tracked with user, timestamp, IP
5. **Input Validation**: UUIDs validated, malformed requests rejected

---

## 📈 Performance Tips

1. **Debounce Rapid Changes**:
```typescript
const debouncedUpdate = debounce(updateSaleCustomer, 300);
```

2. **Cache Customer List**:
```typescript
const { data: customers } = useQuery(
  ['customers', businessId],
  () => fetchCustomers(businessId),
  { staleTime: 5 * 60 * 1000 } // 5 minutes
);
```

3. **Optimistic Updates**:
```typescript
// Update UI immediately, revert on error
setCustomer(newCustomer);
try {
  await updateSaleCustomer(...);
} catch {
  setCustomer(oldCustomer); // Revert
}
```

---

## 📚 Related Documentation

- [Frontend Wholesale Integration](FRONTEND_WHOLESALE_INTEGRATION.md)
- [Sales API Documentation](COMPREHENSIVE_API_DOCUMENTATION.md)
- [Receipt System](RECEIPT_ENDPOINT.md)
- [Audit Logging](AUDIT_LOG.md)

---

## 🎯 Summary

The **Customer Update** endpoint provides a safe, audited way to update customer selection on DRAFT sales. Key features:

✅ **DRAFT-only** updates for security  
✅ **Business boundary** validation  
✅ **Comprehensive audit** trail  
✅ **Clear error** messages  
✅ **Frontend-ready** API design  

This endpoint is essential for POS workflows where customer selection happens after sale creation.

**Endpoint**: `POST/PATCH /sales/api/sales/{sale_id}/update_customer/`

**Committed**: e60b313 on development branch

---

**Last Updated**: October 11, 2025  
**Version**: 1.0.0  
**Status**: ✅ Production Ready
