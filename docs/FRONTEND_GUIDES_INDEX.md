# Frontend Implementation Guides - Index

**Last Updated:** 2025-10-09

This directory contains comprehensive frontend implementation guides for the POS system backend API. Each guide provides TypeScript interfaces, React component examples, and implementation best practices.

---

## Available Guides

### 1. Stock Reconciliation Modal
**File:** [FRONTEND_IMPLEMENTATION_GUIDE.md](./FRONTEND_IMPLEMENTATION_GUIDE.md)

**Purpose:** Displays stock reconciliation snapshot showing warehouse inventory, storefront breakdown, sales, adjustments, and reservations.

**Key Features:**
- Complete API response TypeScript interface
- React component examples for modal display
- Per-storefront breakdown with sellable/reserved metrics
- Formula display showing reconciliation calculation
- Warning states for discrepancies

**API Endpoint:** `GET /inventory/api/products/{id}/stock-reconciliation/`

**When to Use:** When user clicks "View Stock Details" or "Reconciliation" on a product

---

### 2. Stock Adjustment View & Edit
**File:** [STOCK_ADJUSTMENT_EDIT_FRONTEND_GUIDE.md](./STOCK_ADJUSTMENT_EDIT_FRONTEND_GUIDE.md)

**Purpose:** View details of stock adjustments and edit adjustments in PENDING status.

**Key Features:**
- Complete CRUD operations for stock adjustments
- TypeScript interfaces for adjustment data
- React components for view/edit modals
- Status-based permissions (only PENDING can be edited)
- Error handling for edit attempts on locked adjustments
- Support for both full (PUT) and partial (PATCH) updates

**API Endpoints:**
- `GET /inventory/api/stock-adjustments/` - List adjustments
- `GET /inventory/api/stock-adjustments/{id}/` - Get detail
- `POST /inventory/api/stock-adjustments/` - Create new
- `PUT /inventory/api/stock-adjustments/{id}/` - Full update (PENDING only)
- `PATCH /inventory/api/stock-adjustments/{id}/` - Partial update (PENDING only)
- `POST /inventory/api/stock-adjustments/{id}/approve/` - Approve
- `POST /inventory/api/stock-adjustments/{id}/reject/` - Reject
- `POST /inventory/api/stock-adjustments/{id}/complete/` - Complete

**When to Use:** 
- Viewing adjustment history
- Creating new inventory adjustments
- Editing pending adjustments before approval
- Managing adjustment workflow (approve/reject/complete)

---

## Implementation Principles

All guides follow these core principles:

### 1. **No Frontend Calculations**
Backend handles all business logic. Frontend displays values from API responses without transformation.

```typescript
// ❌ DON'T
const warehouseOnHand = recordedBatch - storefrontOnHand;

// ✅ DO
const warehouseOnHand = data.warehouse.inventory_on_hand;
```

### 2. **Status-Based Permissions**
UI respects backend permission rules. For example, only PENDING adjustments can be edited.

```tsx
// ✅ Conditional rendering based on status
{adjustment.status === 'PENDING' && (
  <Button onClick={handleEdit}>Edit</Button>
)}
```

### 3. **Backend Error Messages**
Display error messages from backend responses, don't hardcode generic messages.

```typescript
// ✅ Show backend error
const errorData = await response.json();
toast.error(errorData.error);
```

### 4. **Defensive Coding**
Handle missing/null values gracefully with optional chaining and nullish coalescing.

```typescript
// ✅ Safe access
const firstStore = data.storefront.breakdown[0]?.on_hand ?? 0;
```

### 5. **TypeScript First**
All guides provide complete TypeScript interfaces matching backend serializer output.

```typescript
interface StockAdjustment {
  id: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'COMPLETED';
  // ... full type definitions
}
```

---

## Quick Reference

### Common Response Patterns

#### Pagination
```typescript
interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
```

#### Detail Response
```typescript
interface DetailResponse {
  id: string;
  created_at: string;      // ISO 8601
  updated_at: string;
  // ... entity-specific fields
}
```

#### Error Response
```typescript
interface ErrorResponse {
  error: string;           // Human-readable message
  detail?: string;         // Optional details
  field_errors?: {         // Validation errors
    [field: string]: string[];
  };
}
```

### Common HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | GET, PUT, PATCH successful |
| 201 | Created | POST successful |
| 204 | No Content | DELETE successful |
| 400 | Bad Request | Validation failed, business rule violated |
| 401 | Unauthorized | Missing or invalid auth token |
| 403 | Forbidden | Authenticated but not permitted |
| 404 | Not Found | Resource doesn't exist |
| 500 | Server Error | Backend error (report to dev team) |

### Authentication Header
All authenticated requests must include:
```typescript
headers: {
  'Authorization': `Bearer ${getAuthToken()}`,
  'Content-Type': 'application/json',
}
```

---

## Testing Guidelines

When implementing features from these guides:

### 1. **Test Happy Path**
- Successful data fetching
- Successful updates
- Proper display of all fields

### 2. **Test Edge Cases**
- Empty/null values
- Missing optional fields
- Long text content
- Large numbers

### 3. **Test Error States**
- Network errors (500, timeout)
- Validation errors (400)
- Permission errors (403)
- Not found errors (404)

### 4. **Test Status Transitions**
- For adjustments: PENDING → APPROVED → COMPLETED
- Verify edit button disabled after status change
- Verify error messages when trying to edit locked items

### 5. **Test Responsive Design**
- Mobile view
- Tablet view
- Desktop view
- Modal overflow with long content

---

## Getting Help

### For Implementation Questions:
1. Check the specific guide for your feature
2. Review the TypeScript interfaces carefully
3. Test the endpoint with Postman/curl first
4. Check the network tab to see actual API responses

### For Backend Issues:
1. Share the network request/response
2. Include any error messages
3. Note the endpoint and HTTP method
4. Describe expected vs actual behavior

### For New Features:
If you need a feature not covered in these guides:
1. Check if the backend endpoint exists
2. Request documentation if endpoint is undocumented
3. Work with backend team to add the feature if it doesn't exist

---

## Document Maintenance

These guides are **living documents**. When backend changes occur:

- ✅ Update TypeScript interfaces to match new serializer fields
- ✅ Add new endpoints or remove deprecated ones
- ✅ Update examples if patterns change
- ✅ Add new guides for new features

**Last Review:** 2025-10-09  
**Next Review:** When backend API changes are deployed

---

## Contributing

When adding new guides, follow this template:

1. **Title** - Clear, descriptive name
2. **Purpose** - What this feature does
3. **API Endpoints** - All relevant endpoints
4. **TypeScript Interfaces** - Complete type definitions
5. **React Examples** - Working component code
6. **Key Rules** - Do's and don'ts
7. **Error Handling** - Common error scenarios
8. **Testing Checklist** - What to verify

Keep guides:
- **Practical** - Real code examples, not pseudocode
- **Complete** - All required information in one place
- **Clear** - Explain why, not just how
- **Current** - Update when backend changes

---

## Version History

| Date | Guide | Changes |
|------|-------|---------|
| 2025-10-09 | Stock Adjustment Edit | Initial release - view/edit functionality |
| 2025-10-09 | Stock Reconciliation | Updated storefront breakdown structure |
| 2025-10-09 | Index | Created master index document |

---

**Happy coding! 🚀**

For questions or clarifications, contact the backend team.
