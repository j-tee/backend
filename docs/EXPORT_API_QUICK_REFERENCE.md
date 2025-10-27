# Export Automation API - Quick Reference Card

## Base URL
```
/reports/api/automation/
```

## Authentication
All endpoints require JWT token:
```
Authorization: Bearer {token}
```

---

## Endpoints Summary

### 📅 Schedules (`/schedules/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/schedules/` | List all schedules |
| POST | `/schedules/` | Create new schedule |
| GET | `/schedules/{id}/` | Get schedule details |
| PUT | `/schedules/{id}/` | Update schedule |
| PATCH | `/schedules/{id}/` | Partial update |
| DELETE | `/schedules/{id}/` | Delete schedule |
| POST | `/schedules/{id}/activate/` | Activate schedule |
| POST | `/schedules/{id}/deactivate/` | Deactivate schedule |
| POST | `/schedules/{id}/trigger/` | Run now |
| GET | `/schedules/upcoming/` | Next 10 runs |
| GET | `/schedules/overdue/` | Overdue schedules |

### 📊 History (`/history/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/history/` | List export history (paginated) |
| GET | `/history/{id}/` | Get execution details |
| GET | `/history/{id}/download/` | Download export file |
| GET | `/history/statistics/` | Export statistics |
| GET | `/history/recent/` | Last 10 exports |

### 🔔 Notifications (`/notifications/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/notifications/` | Get settings |
| PUT | `/notifications/` | Update settings |

---

## Request Examples

### Create Daily Schedule
```json
POST /reports/api/automation/schedules/

{
  "name": "Daily Sales Report",
  "export_type": "SALES",
  "format": "excel",
  "frequency": "DAILY",
  "hour": 8,
  "recipients": ["accounting@company.com"],
  "include_creator_email": true,
  "filters": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  },
  "is_active": true
}
```

### Create Weekly Schedule
```json
POST /reports/api/automation/schedules/

{
  "name": "Weekly Customer List",
  "export_type": "CUSTOMERS",
  "format": "csv",
  "frequency": "WEEKLY",
  "hour": 9,
  "day_of_week": 0,  // Monday
  "recipients": ["sales@company.com"],
  "include_creator_email": false,
  "filters": {
    "include_credit_history": true
  },
  "is_active": true
}
```

### Create Monthly Schedule
```json
POST /reports/api/automation/schedules/

{
  "name": "Monthly Inventory Report",
  "export_type": "INVENTORY",
  "format": "pdf",
  "frequency": "MONTHLY",
  "hour": 0,
  "day_of_month": 1,  // 1st of month
  "recipients": ["inventory@company.com"],
  "filters": {
    "exclude_zero_value": true
  },
  "is_active": true
}
```

---

## Field Reference

### Export Types
- `SALES` - Sales transactions
- `CUSTOMERS` - Customer list with credit info
- `INVENTORY` - Stock levels and valuation
- `AUDIT_LOGS` - System audit trail

### Formats
- `excel` - Excel workbook (.xlsx)
- `csv` - CSV file (.csv)
- `pdf` - PDF report (.pdf)

### Frequencies
- `DAILY` - Every day at specified hour
- `WEEKLY` - Specific day of week at specified hour
- `MONTHLY` - Specific day of month at specified hour

### Day of Week (for WEEKLY)
- `0` = Monday
- `1` = Tuesday
- `2` = Wednesday
- `3` = Thursday
- `4` = Friday
- `5` = Saturday
- `6` = Sunday

### Day of Month (for MONTHLY)
- `1-28` (limited to 28 for safety)

### Export Status
- `PENDING` - Queued for execution
- `PROCESSING` - Currently running
- `COMPLETED` - Finished successfully
- `FAILED` - Error occurred
- `EMAILED` - Successfully sent via email

### Trigger Types
- `MANUAL` - User clicked "Run Now"
- `SCHEDULED` - Automatic execution
- `API` - Triggered via API

---

## Filter Requirements

### SALES Exports
**Required:**
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)

**Optional:**
- `storefront_id` (UUID)
- `customer_type` (RETAIL/WHOLESALE)
- `status` (PENDING/COMPLETED/etc)

### AUDIT_LOGS Exports
**Required:**
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)

**Optional:**
- `event_type` (string)
- `user_id` (UUID)

### CUSTOMERS Exports
**All Optional:**
- `customer_type` (RETAIL/WHOLESALE)
- `credit_status` (active/blocked/overdue)
- `min_outstanding_balance` (decimal)
- `include_credit_history` (boolean)

### INVENTORY Exports
**All Optional:**
- `storefront_id` (UUID)
- `category` (string)
- `stock_status` (in_stock/low_stock/out_of_stock)
- `min_quantity` (integer)
- `exclude_zero_value` (boolean)

---

## Query Parameters

### List Schedules
```
GET /reports/api/automation/schedules/?is_active=true&export_type=SALES
```
- `is_active` (boolean)
- `export_type` (SALES/CUSTOMERS/INVENTORY/AUDIT_LOGS)
- `frequency` (DAILY/WEEKLY/MONTHLY)

### List History
```
GET /reports/api/automation/history/?status=COMPLETED&page=1&page_size=20
```
- `export_type` (SALES/CUSTOMERS/INVENTORY/AUDIT_LOGS)
- `format` (excel/csv/pdf)
- `status` (PENDING/PROCESSING/COMPLETED/FAILED/EMAILED)
- `trigger` (MANUAL/SCHEDULED/API)
- `schedule_id` (UUID)
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)
- `page` (integer, default: 1)
- `page_size` (integer, default: 20, max: 100)

---

## Response Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 201 | Created | Resource created successfully |
| 204 | No Content | Delete successful |
| 400 | Bad Request | Check validation errors |
| 401 | Unauthorized | Re-authenticate |
| 404 | Not Found | Resource doesn't exist |
| 500 | Server Error | Retry or report bug |

---

## Common Validation Errors

### Schedule Creation
```json
{
  "detail": "Validation failed",
  "errors": {
    "day_of_week": ["Day of week is required for weekly schedules"],
    "recipients": ["Invalid email address: bad-email"],
    "filters": ["Sales exports require start_date and end_date in filters"]
  }
}
```

### Email Validation
```json
{
  "errors": {
    "recipients": ["Invalid email address: user@invalid"]
  }
}
```

### Timing Validation
```json
{
  "errors": {
    "hour": ["Hour must be between 0 and 23"],
    "day_of_month": ["Day of month must be between 1 and 28"]
  }
}
```

---

## Helpful Computed Fields

Schedules include:
- `next_run_display` - "In 2 hours", "In 3 days"
- `last_run_display` - "Never run", "2 days ago"
- `status_display` - "Active", "Inactive", "Overdue"

History includes:
- `duration_display` - "45s", "2m 15s"
- `file_size_display` - "1.5 MB", "500 KB"
- `status_display` - User-friendly status text
- `duration_seconds` - Numeric execution time
- `file_size_mb` - File size in megabytes

---

## File Download

```javascript
// Download export file
const response = await fetch(
  `/reports/api/automation/history/${id}/download/`,
  { headers: { 'Authorization': `Bearer ${token}` } }
);

const blob = await response.blob();
const filename = response.headers
  .get('Content-Disposition')
  .split('filename=')[1]
  .replace(/"/g, '');

// Trigger download
const url = window.URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = filename;
a.click();
window.URL.revokeObjectURL(url);
```

---

## Statistics Response

```json
{
  "total_exports": 1250,
  "successful_exports": 1200,
  "failed_exports": 50,
  "success_rate": 96.0,
  "by_type": {
    "SALES": { "total": 400, "successful": 395, "failed": 5 },
    "CUSTOMERS": { "total": 300, "successful": 298, "failed": 2 }
  },
  "by_format": {
    "excel": { "total": 600, "successful": 590, "failed": 10 },
    "csv": { "total": 400, "successful": 395, "failed": 5 },
    "pdf": { "total": 250, "successful": 215, "failed": 35 }
  },
  "recent_exports_7_days": 45,
  "average_file_size_mb": 2.35
}
```

---

## Pagination

```json
{
  "count": 150,
  "next": "http://.../history/?page=2",
  "previous": null,
  "results": [...]
}
```

Navigate:
- `next` - URL for next page (null if last page)
- `previous` - URL for previous page (null if first page)
- `count` - Total number of items

---

## Tips

1. **All times are UTC** - Convert to local time for display
2. **Use pagination** - History can have thousands of records
3. **Poll for updates** - Check status every 5 seconds for pending exports
4. **Validate emails** - Before submitting schedule forms
5. **Show timezone info** - "8:00 UTC (3:00 AM local)"
6. **Disable actions** - Download only for COMPLETED exports
7. **Handle errors gracefully** - Show user-friendly messages
8. **Cache statistics** - Refresh every 5 minutes

---

**Quick Support:**
- Full Documentation: `PHASE_6_UI_INTEGRATION_GUIDE.md`
- Backend Issues: Create GitHub issue
- Questions: Contact backend team

**Last Updated:** October 12, 2024
