# Transfer Deletion API - Quick Reference

## Endpoint

```http
DELETE /inventory/api/warehouse-transfers/{id}/
DELETE /inventory/api/storefront-transfers/{id}/
```

## Request

**Headers:**
```http
Authorization: Token {your-auth-token}
Content-Type: application/json
```

**No request body required**

## Responses

### Success (204 No Content)

```http
HTTP/1.1 204 No Content
```

Transfer successfully deleted. No response body.

### Error: Completed Transfer (400 Bad Request)

```json
{
  "error": "Cannot delete a completed transfer. Use the cancellation process first, or create a reversal transfer instead."
}
```

### Error: Insufficient Permissions (403 Forbidden)

```json
{
  "detail": "Only business owners and administrators can delete transfers."
}
```

### Error: Not Found (404 Not Found)

```json
{
  "detail": "Not found."
}
```

## Quick Implementation

### JavaScript/TypeScript

```typescript
// Service
export const deleteTransfer = async (transferId: string): Promise<void> => {
  const response = await fetch(`/inventory/api/warehouse-transfers/${transferId}/`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Token ${getAuthToken()}`,
      'Content-Type': 'application/json',
    },
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.error || error.detail || 'Failed to delete transfer')
  }
}

// Usage
try {
  await deleteTransfer(transferId)
  console.log('Transfer deleted successfully')
  // Refresh list or redirect
} catch (error) {
  console.error('Delete failed:', error.message)
  // Show error to user
}
```

### Axios

```typescript
import axios from 'axios'

export const deleteTransfer = async (transferId: string): Promise<void> => {
  await axios.delete(`/inventory/api/warehouse-transfers/${transferId}/`)
}

// Usage
try {
  await deleteTransfer(transferId)
  toast.success('Transfer deleted successfully')
} catch (error) {
  toast.error(error.response?.data?.error || 'Failed to delete transfer')
}
```

## Rules

### Who Can Delete?
- ✅ Business OWNER
- ✅ Business ADMIN  
- ❌ MANAGER
- ❌ STAFF

### What Can Be Deleted?
- ✅ Pending transfers
- ✅ In-transit transfers
- ✅ Cancelled transfers
- ❌ Completed transfers

## UI Guidelines

### Button State

```tsx
<Button
  variant="danger"
  onClick={handleDelete}
  disabled={transfer.status === 'completed'}
>
  Delete Transfer
</Button>
```

### Confirmation Dialog

**Must include:**
- ⚠️ Warning message
- Transfer reference number
- "This cannot be undone" text
- Optional: Reason field (min 10 chars)

**Example:**

```tsx
<Modal>
  <Alert variant="danger">
    <strong>⚠️ Warning:</strong> This will permanently delete transfer{' '}
    <code>{transfer.reference_number}</code>. This action cannot be undone.
  </Alert>
  
  <Form.Control
    as="textarea"
    placeholder="Reason for deletion (optional)"
    value={reason}
    onChange={(e) => setReason(e.target.value)}
  />
  
  <Button onClick={confirmDelete}>Delete</Button>
</Modal>
```

## Testing Checklist

- [ ] Delete pending transfer → success
- [ ] Delete in-transit transfer → success
- [ ] Delete cancelled transfer → success
- [ ] Try to delete completed transfer → error 400
- [ ] Try to delete as STAFF user → error 403
- [ ] Transfer disappears from list after deletion
- [ ] Error messages display correctly
- [ ] Confirmation modal works
- [ ] Loading states during deletion

## Common Issues

### Issue: Getting 403 Forbidden
**Cause:** User doesn't have OWNER or ADMIN role  
**Solution:** Check user's business membership role

### Issue: Getting 400 "Cannot delete completed transfer"
**Cause:** Transfer status is "completed"  
**Solution:** Use cancel endpoint first, or create reversal transfer

### Issue: Getting 404 Not Found
**Cause:** Transfer doesn't exist or user doesn't have access  
**Solution:** Verify transfer ID and user's business membership

## See Also

- [TRANSFER_DELETION_IMPLEMENTATION.md](./TRANSFER_DELETION_IMPLEMENTATION.md) - Full implementation details
- [API_ENDPOINTS_REFERENCE.md](./API_ENDPOINTS_REFERENCE.md) - All transfer endpoints
- [PHASE_4_API_REFERENCE.md](./PHASE_4_API_REFERENCE.md) - Transfer API documentation
