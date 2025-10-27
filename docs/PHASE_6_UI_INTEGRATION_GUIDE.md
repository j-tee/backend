# Phase 6: UI Integration Guide - Export Automation Frontend

## Overview

This guide provides everything the frontend team needs to integrate the Export Automation system into the UI. All backend APIs are fully functional and production-ready.

**Target Audience:** Frontend Developers  
**Backend Status:** ✅ Complete and Operational  
**API Base URL:** `/reports/api/automation/`

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [API Endpoints Reference](#api-endpoints-reference)
4. [Data Models](#data-models)
5. [UI Components Needed](#ui-components-needed)
6. [User Workflows](#user-workflows)
7. [API Usage Examples](#api-usage-examples)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)
10. [Testing Guidance](#testing-guidance)

---

## Quick Start

### Base Configuration

```javascript
const API_BASE_URL = '/reports/api/automation';

// All requests require authentication token
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};
```

### Key Concepts

1. **Export Schedules** - Configurations for automated exports
2. **Export History** - Records of all export executions
3. **Notification Settings** - Email preferences per business

---

## Authentication

All endpoints require authentication via JWT token in the Authorization header.

```javascript
headers: {
  'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGc...',
  'Content-Type': 'application/json'
}
```

**Business Filtering:** Automatic - Users only see data for businesses they're members of.

---

## API Endpoints Reference

### 1. Export Schedules

#### List All Schedules

**Endpoint:** `GET /reports/api/automation/schedules/`

**Query Parameters:**
- `is_active` (boolean): Filter by active/inactive status
- `export_type` (string): Filter by type (`SALES`, `CUSTOMERS`, `INVENTORY`, `AUDIT_LOGS`)
- `frequency` (string): Filter by frequency (`DAILY`, `WEEKLY`, `MONTHLY`)

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Daily Sales Report",
    "export_type": "SALES",
    "format": "excel",
    "frequency": "DAILY",
    "hour": 8,
    "day_of_week": null,
    "day_of_month": null,
    "recipients": ["accounting@company.com", "manager@company.com"],
    "include_creator_email": true,
    "email_subject": "Daily Sales Report",
    "email_message": "Please find attached the daily sales export.",
    "filters": {
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    },
    "is_active": true,
    "last_run_at": "2024-10-12T08:00:00Z",
    "next_run_at": "2024-10-13T08:00:00Z",
    "created_at": "2024-10-01T10:30:00Z",
    "updated_at": "2024-10-01T10:30:00Z",
    "created_by": "user-uuid",
    "created_by_name": "John Doe",
    "next_run_display": "In 16 hours",
    "last_run_display": "8 hours ago",
    "status_display": "Active"
  }
]
```

#### Create Schedule

**Endpoint:** `POST /reports/api/automation/schedules/`

**Request Body:**
```json
{
  "name": "Daily Sales Report",
  "export_type": "SALES",
  "format": "excel",
  "frequency": "DAILY",
  "hour": 8,
  "recipients": ["accounting@company.com"],
  "include_creator_email": true,
  "email_subject": "Daily Sales Report",
  "email_message": "Attached is today's sales report.",
  "filters": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  },
  "is_active": true
}
```

**Validation Rules:**
- `name`: Required, max 255 characters
- `export_type`: Required, choices: `SALES`, `CUSTOMERS`, `INVENTORY`, `AUDIT_LOGS`
- `format`: Required, choices: `excel`, `csv`, `pdf`
- `frequency`: Required, choices: `DAILY`, `WEEKLY`, `MONTHLY`
- `hour`: Required, 0-23 (UTC time)
- `day_of_week`: Required if frequency=WEEKLY (0=Monday, 6=Sunday)
- `day_of_month`: Required if frequency=MONTHLY (1-28)
- `recipients`: List of valid email addresses
- `filters`: Required fields vary by export_type:
  - `SALES`: Requires `start_date`, `end_date`
  - `AUDIT_LOGS`: Requires `start_date`, `end_date`
  - `CUSTOMERS`: Optional filters
  - `INVENTORY`: Optional filters

**Response:** Same as list response (single object)

**Status Code:** `201 Created`

#### Get Schedule Details

**Endpoint:** `GET /reports/api/automation/schedules/{id}/`

**Response:** Same as list response (single object)

#### Update Schedule

**Endpoint:** `PUT /reports/api/automation/schedules/{id}/`

**Request Body:** Same as create (all fields required)

**Response:** Updated schedule object

**Note:** If timing fields change (frequency, hour, day_of_week, day_of_month), `next_run_at` is automatically recalculated.

#### Partial Update Schedule

**Endpoint:** `PATCH /reports/api/automation/schedules/{id}/`

**Request Body:** Only fields to update

```json
{
  "is_active": false,
  "recipients": ["new-email@company.com"]
}
```

#### Delete Schedule

**Endpoint:** `DELETE /reports/api/automation/schedules/{id}/`

**Response:** `204 No Content`

#### Activate Schedule

**Endpoint:** `POST /reports/api/automation/schedules/{id}/activate/`

**Response:**
```json
{
  "id": "...",
  "is_active": true,
  "next_run_at": "2024-10-13T08:00:00Z",
  ...
}
```

**Status Code:** `200 OK`

**Error:** `400 Bad Request` if already active

#### Deactivate Schedule

**Endpoint:** `POST /reports/api/automation/schedules/{id}/deactivate/`

**Response:**
```json
{
  "id": "...",
  "is_active": false,
  "next_run_at": null,
  ...
}
```

#### Manually Trigger Schedule

**Endpoint:** `POST /reports/api/automation/schedules/{id}/trigger/`

**Request Body:**
```json
{
  "schedule_id": "550e8400-e29b-41d4-a716-446655440000",
  "send_email": true,
  "override_recipients": ["optional@email.com"]
}
```

**Response:** Export history object
```json
{
  "id": "history-uuid",
  "export_type": "SALES",
  "format": "excel",
  "trigger": "MANUAL",
  "status": "COMPLETED",
  "file_name": "sales_export_2024-10-12.xlsx",
  "record_count": 45,
  ...
}
```

**Status Code:** `201 Created`

#### Get Upcoming Exports

**Endpoint:** `GET /reports/api/automation/schedules/upcoming/`

**Response:** List of next 10 scheduled exports (sorted by `next_run_at`)

#### Get Overdue Exports

**Endpoint:** `GET /reports/api/automation/schedules/overdue/`

**Response:** List of schedules past their `next_run_at` time

---

### 2. Export History

#### List Export History

**Endpoint:** `GET /reports/api/automation/history/`

**Query Parameters:**
- `export_type`: Filter by type
- `format`: Filter by format (`excel`, `csv`, `pdf`)
- `status`: Filter by status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`, `EMAILED`)
- `trigger`: Filter by trigger (`MANUAL`, `SCHEDULED`, `API`)
- `schedule_id`: Filter by specific schedule
- `start_date`: Filter by created_at >= date
- `end_date`: Filter by created_at <= date
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

**Response:**
```json
{
  "count": 150,
  "next": "http://reports/api/automation/history/?page=2",
  "previous": null,
  "results": [
    {
      "id": "history-uuid",
      "export_type": "SALES",
      "format": "excel",
      "trigger": "SCHEDULED",
      "status": "COMPLETED",
      "started_at": "2024-10-12T08:00:00Z",
      "completed_at": "2024-10-12T08:00:05Z",
      "created_at": "2024-10-12T08:00:00Z",
      "file_name": "sales_export_2024-10-12.xlsx",
      "file_size": 15234,
      "file_path": "exports/business-id/2024/10/...",
      "record_count": 45,
      "filters_applied": {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
      },
      "email_sent": true,
      "email_recipients": ["accounting@company.com"],
      "email_sent_at": "2024-10-12T08:00:06Z",
      "error_message": null,
      "user": "user-uuid",
      "user_name": "John Doe",
      "schedule": "schedule-uuid",
      "schedule_name": "Daily Sales Report",
      "duration_display": "5s",
      "file_size_display": "14.87 KB",
      "status_display": "Emailed",
      "duration_seconds": 5.2,
      "file_size_mb": 0.01
    }
  ]
}
```

#### Get Export Details

**Endpoint:** `GET /reports/api/automation/history/{id}/`

**Response:** Single history object (includes `error_traceback` if failed)

```json
{
  "id": "...",
  "error_traceback": "Traceback (most recent call last):\n  File ...",
  ...
}
```

#### Download Export File

**Endpoint:** `GET /reports/api/automation/history/{id}/download/`

**Response:** Binary file download

**Headers:**
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="sales_export_2024-10-12.xlsx"
```

**Status Codes:**
- `200 OK`: File downloaded
- `404 Not Found`: File not available
- `400 Bad Request`: Export not complete

**Note:** Only available for exports with status `COMPLETED` or `EMAILED`

#### Get Export Statistics

**Endpoint:** `GET /reports/api/automation/history/statistics/`

**Response:**
```json
{
  "total_exports": 1250,
  "successful_exports": 1200,
  "failed_exports": 50,
  "success_rate": 96.0,
  "by_type": {
    "SALES": {
      "total": 400,
      "successful": 395,
      "failed": 5
    },
    "CUSTOMERS": {
      "total": 300,
      "successful": 298,
      "failed": 2
    },
    "INVENTORY": {
      "total": 350,
      "successful": 340,
      "failed": 10
    },
    "AUDIT_LOGS": {
      "total": 200,
      "successful": 167,
      "failed": 33
    }
  },
  "by_format": {
    "excel": {
      "total": 600,
      "successful": 590,
      "failed": 10
    },
    "csv": {
      "total": 400,
      "successful": 395,
      "failed": 5
    },
    "pdf": {
      "total": 250,
      "successful": 215,
      "failed": 35
    }
  },
  "recent_exports_7_days": 45,
  "average_file_size_mb": 2.35
}
```

#### Get Recent Exports

**Endpoint:** `GET /reports/api/automation/history/recent/`

**Response:** List of last 10 exports

---

### 3. Notification Settings

#### Get Notification Settings

**Endpoint:** `GET /reports/api/automation/notifications/`

**Response:**
```json
{
  "notify_on_success": true,
  "notify_on_failure": true,
  "default_recipients": ["admin@company.com", "manager@company.com"],
  "from_name": "POS Export Service",
  "reply_to_email": "noreply@company.com"
}
```

**Note:** Settings are created automatically with defaults if not exists.

#### Update Notification Settings

**Endpoint:** `PUT /reports/api/automation/notifications/`

**Request Body:**
```json
{
  "notify_on_success": false,
  "notify_on_failure": true,
  "default_recipients": ["admin@company.com"],
  "from_name": "My Company Exports",
  "reply_to_email": "support@company.com"
}
```

**Response:** Updated settings object

---

## Data Models

### ExportSchedule

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | Unique identifier |
| name | String | Yes | Schedule name (max 255) |
| export_type | String | Yes | SALES, CUSTOMERS, INVENTORY, AUDIT_LOGS |
| format | String | Yes | excel, csv, pdf |
| frequency | String | Yes | DAILY, WEEKLY, MONTHLY |
| hour | Integer | Yes | Hour of day (0-23, UTC) |
| day_of_week | Integer | Conditional | 0-6 (Monday-Sunday), required if WEEKLY |
| day_of_month | Integer | Conditional | 1-28, required if MONTHLY |
| recipients | Array | Yes | List of email addresses |
| include_creator_email | Boolean | No | Default: false |
| email_subject | String | No | Custom email subject |
| email_message | Text | No | Custom email message |
| filters | JSON | Yes | Export-specific filters |
| is_active | Boolean | No | Default: true |
| last_run_at | DateTime | Auto | Last execution time |
| next_run_at | DateTime | Auto | Next scheduled time |
| created_at | DateTime | Auto | Creation timestamp |
| updated_at | DateTime | Auto | Last update timestamp |
| created_by | UUID | Auto | Creator user ID |

### ExportHistory

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| export_type | String | Type of export |
| format | String | Export format |
| trigger | String | MANUAL, SCHEDULED, API |
| status | String | PENDING, PROCESSING, COMPLETED, FAILED, EMAILED |
| started_at | DateTime | Execution start time |
| completed_at | DateTime | Execution end time |
| file_name | String | Name of generated file |
| file_size | Integer | File size in bytes |
| file_path | String | Storage path |
| record_count | Integer | Number of records exported |
| filters_applied | JSON | Filters used |
| email_sent | Boolean | Whether email was sent |
| email_recipients | Array | Recipients list |
| email_sent_at | DateTime | Email send time |
| error_message | Text | Error description if failed |
| error_traceback | Text | Full error traceback |
| user | UUID | User who triggered |
| schedule | UUID | Related schedule (if scheduled) |
| created_at | DateTime | Record creation time |

**Computed Fields:**
- `duration_seconds`: Execution time in seconds
- `file_size_mb`: File size in megabytes
- `duration_display`: Human-readable duration ("45s", "2m 15s")
- `file_size_display`: Human-readable size ("1.5 MB")
- `status_display`: User-friendly status text

### ExportNotificationSettings

| Field | Type | Description |
|-------|------|-------------|
| notify_on_success | Boolean | Send email on success |
| notify_on_failure | Boolean | Send email on failure |
| default_recipients | Array | Default email list |
| from_name | String | Email sender name |
| reply_to_email | String | Reply-to address |

---

## UI Components Needed

### 1. Schedule Management Page

**Components:**
- **ScheduleList** - Table/grid of all schedules
- **ScheduleForm** - Create/edit schedule form
- **ScheduleCard** - Individual schedule display
- **FrequencySelector** - Daily/Weekly/Monthly picker
- **FilterBuilder** - Dynamic filter configuration based on export type
- **RecipientManager** - Email list management

**Features:**
- Create new schedule
- Edit existing schedule
- Delete schedule
- Activate/deactivate toggle
- Manual trigger button
- Filter schedules by type/status
- Sort by name, type, next run, etc.

### 2. Export History Page

**Components:**
- **HistoryTable** - Paginated list of exports
- **HistoryFilters** - Multi-filter sidebar
- **HistoryDetails** - Detailed view of single export
- **DownloadButton** - File download action
- **StatusBadge** - Visual status indicator
- **ErrorDisplay** - Error message viewer

**Features:**
- Paginated history list (20 per page)
- Filter by type, format, status, date range
- Download completed exports
- View execution details
- See error messages for failed exports
- Retry failed exports

### 3. Statistics Dashboard

**Components:**
- **StatCard** - Individual metric display
- **SuccessRateChart** - Visual success rate
- **ExportTypeBreakdown** - Pie/bar chart by type
- **FormatBreakdown** - Distribution by format
- **RecentActivity** - Timeline of recent exports

**Metrics to Display:**
- Total exports
- Success rate
- Failed exports count
- Breakdown by type
- Breakdown by format
- Recent activity (7 days)
- Average file size

### 4. Notification Settings Panel

**Components:**
- **NotificationToggles** - Success/failure switches
- **EmailListEditor** - Manage default recipients
- **EmailSettings** - From name and reply-to

**Features:**
- Toggle success notifications
- Toggle failure notifications
- Manage default recipients
- Customize from name
- Set reply-to email

### 5. Common Components

**Reusable:**
- **ExportTypeSelector** - Dropdown for SALES/CUSTOMERS/INVENTORY/AUDIT_LOGS
- **FormatSelector** - Dropdown for excel/csv/pdf
- **FrequencySelector** - Daily/Weekly/Monthly picker
- **TimeSelector** - Hour picker (with timezone display)
- **DayOfWeekSelector** - Monday-Sunday picker
- **DayOfMonthSelector** - 1-28 picker
- **EmailInput** - Email validation input
- **StatusBadge** - Color-coded status display
- **CountdownTimer** - Next run countdown

---

## User Workflows

### Workflow 1: Create Daily Sales Export

1. User clicks "Create Schedule"
2. Form displays:
   - Name: "Daily Sales Report"
   - Export Type: Select "Sales"
   - Format: Select "Excel"
   - Frequency: Select "Daily"
   - Hour: Select "8" (8 AM UTC)
   - Recipients: Add emails
   - Filters: Date range required
3. User fills form and clicks "Create"
4. API call: `POST /reports/api/automation/schedules/`
5. On success: Show schedule in list with "Active" badge
6. Display next run time: "Next run: In 14 hours"

### Workflow 2: View Export History

1. User navigates to "Export History"
2. API call: `GET /reports/api/automation/history/?page=1`
3. Display paginated table with:
   - Export type
   - Format
   - Status (with color badge)
   - Date/time
   - Record count
   - File size
   - Download button (if completed)
4. User clicks filter by "Failed" status
5. API call: `GET /reports/api/automation/history/?status=FAILED`
6. Display only failed exports

### Workflow 3: Download Past Export

1. User finds completed export in history
2. Clicks "Download" button
3. API call: `GET /reports/api/automation/history/{id}/download/`
4. Browser downloads file with original filename

### Workflow 4: Manually Trigger Schedule

1. User views schedule list
2. Clicks "Run Now" button on a schedule
3. Confirmation modal: "Run Daily Sales Report now?"
4. User confirms
5. API call: `POST /reports/api/automation/schedules/{id}/trigger/`
6. Show loading indicator
7. On completion: Navigate to history page showing new export

### Workflow 5: Configure Notifications

1. User navigates to Settings
2. API call: `GET /reports/api/automation/notifications/`
3. Display current settings
4. User toggles "Notify on success" to OFF
5. User adds new default recipient
6. User clicks "Save"
7. API call: `PUT /reports/api/automation/notifications/`
8. Show success message

---

## API Usage Examples

### Example 1: Create Weekly Schedule (React)

```javascript
const createWeeklySchedule = async (formData) => {
  try {
    const response = await fetch('/reports/api/automation/schedules/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: formData.name,
        export_type: 'CUSTOMERS',
        format: 'csv',
        frequency: 'WEEKLY',
        hour: 9,
        day_of_week: 0, // Monday
        recipients: formData.recipients,
        include_creator_email: true,
        filters: {
          include_credit_history: true
        },
        is_active: true
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create schedule');
    }

    const schedule = await response.json();
    console.log('Schedule created:', schedule);
    return schedule;
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
};
```

### Example 2: Fetch and Display History (Vue.js)

```javascript
<template>
  <div>
    <table>
      <thead>
        <tr>
          <th>Type</th>
          <th>Format</th>
          <th>Status</th>
          <th>Date</th>
          <th>Records</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in history" :key="item.id">
          <td>{{ item.export_type }}</td>
          <td>{{ item.format }}</td>
          <td><span :class="statusClass(item.status)">{{ item.status_display }}</span></td>
          <td>{{ formatDate(item.created_at) }}</td>
          <td>{{ item.record_count }}</td>
          <td>
            <button 
              v-if="item.status === 'COMPLETED' || item.status === 'EMAILED'"
              @click="downloadExport(item.id)">
              Download
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  data() {
    return {
      history: [],
      loading: false
    };
  },
  async mounted() {
    await this.fetchHistory();
  },
  methods: {
    async fetchHistory() {
      this.loading = true;
      try {
        const response = await fetch('/reports/api/automation/history/', {
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        });
        const data = await response.json();
        this.history = data.results;
      } catch (error) {
        console.error('Error fetching history:', error);
      } finally {
        this.loading = false;
      }
    },
    async downloadExport(id) {
      try {
        const response = await fetch(`/reports/api/automation/history/${id}/download/`, {
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        });
        
        if (!response.ok) throw new Error('Download failed');
        
        const blob = await response.blob();
        const filename = response.headers.get('Content-Disposition')
          .split('filename=')[1]
          .replace(/"/g, '');
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
      } catch (error) {
        console.error('Error downloading:', error);
      }
    },
    statusClass(status) {
      const classes = {
        'COMPLETED': 'status-success',
        'EMAILED': 'status-success',
        'FAILED': 'status-error',
        'PROCESSING': 'status-warning',
        'PENDING': 'status-info'
      };
      return classes[status] || '';
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleString();
    }
  }
};
</script>
```

### Example 3: Statistics Dashboard (Angular)

```typescript
import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';

interface ExportStats {
  total_exports: number;
  successful_exports: number;
  failed_exports: number;
  success_rate: number;
  by_type: Record<string, any>;
  by_format: Record<string, any>;
  recent_exports_7_days: number;
  average_file_size_mb: number;
}

@Component({
  selector: 'app-export-statistics',
  template: `
    <div class="stats-dashboard">
      <div class="stat-card">
        <h3>Total Exports</h3>
        <p class="stat-value">{{ stats?.total_exports || 0 }}</p>
      </div>
      
      <div class="stat-card">
        <h3>Success Rate</h3>
        <p class="stat-value">{{ stats?.success_rate || 0 }}%</p>
      </div>
      
      <div class="stat-card">
        <h3>Failed Exports</h3>
        <p class="stat-value error">{{ stats?.failed_exports || 0 }}</p>
      </div>
      
      <div class="stat-card">
        <h3>Recent (7 days)</h3>
        <p class="stat-value">{{ stats?.recent_exports_7_days || 0 }}</p>
      </div>
      
      <div class="breakdown">
        <h3>By Type</h3>
        <div *ngFor="let type of getTypes()">
          <span>{{ type }}:</span>
          <span>{{ stats?.by_type[type]?.successful || 0 }} / {{ stats?.by_type[type]?.total || 0 }}</span>
        </div>
      </div>
    </div>
  `
})
export class ExportStatisticsComponent implements OnInit {
  stats: ExportStats | null = null;

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.fetchStatistics();
  }

  fetchStatistics() {
    this.http.get<ExportStats>('/reports/api/automation/history/statistics/')
      .subscribe(
        data => {
          this.stats = data;
        },
        error => {
          console.error('Error fetching statistics:', error);
        }
      );
  }

  getTypes(): string[] {
    return this.stats ? Object.keys(this.stats.by_type) : [];
  }
}
```

### Example 4: Schedule Form Validation

```javascript
// Validation helper for schedule creation
const validateScheduleForm = (formData) => {
  const errors = {};

  // Name validation
  if (!formData.name || formData.name.trim().length === 0) {
    errors.name = 'Schedule name is required';
  } else if (formData.name.length > 255) {
    errors.name = 'Name must be less than 255 characters';
  }

  // Export type validation
  const validTypes = ['SALES', 'CUSTOMERS', 'INVENTORY', 'AUDIT_LOGS'];
  if (!validTypes.includes(formData.export_type)) {
    errors.export_type = 'Invalid export type';
  }

  // Format validation
  const validFormats = ['excel', 'csv', 'pdf'];
  if (!validFormats.includes(formData.format)) {
    errors.format = 'Invalid format';
  }

  // Frequency validation
  const validFrequencies = ['DAILY', 'WEEKLY', 'MONTHLY'];
  if (!validFrequencies.includes(formData.frequency)) {
    errors.frequency = 'Invalid frequency';
  }

  // Hour validation
  if (formData.hour < 0 || formData.hour > 23) {
    errors.hour = 'Hour must be between 0 and 23';
  }

  // Frequency-specific validation
  if (formData.frequency === 'WEEKLY') {
    if (formData.day_of_week === null || formData.day_of_week < 0 || formData.day_of_week > 6) {
      errors.day_of_week = 'Day of week is required for weekly schedules (0-6)';
    }
  }

  if (formData.frequency === 'MONTHLY') {
    if (formData.day_of_month === null || formData.day_of_month < 1 || formData.day_of_month > 28) {
      errors.day_of_month = 'Day of month is required for monthly schedules (1-28)';
    }
  }

  // Recipients validation
  if (!formData.recipients || formData.recipients.length === 0) {
    errors.recipients = 'At least one recipient email is required';
  } else {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const invalidEmails = formData.recipients.filter(email => !emailRegex.test(email));
    if (invalidEmails.length > 0) {
      errors.recipients = `Invalid email addresses: ${invalidEmails.join(', ')}`;
    }
  }

  // Export-type specific filter validation
  if (formData.export_type === 'SALES' || formData.export_type === 'AUDIT_LOGS') {
    if (!formData.filters?.start_date || !formData.filters?.end_date) {
      errors.filters = `${formData.export_type} exports require start_date and end_date in filters`;
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  };
};
```

---

## Error Handling

### Common Error Responses

#### Validation Error (400 Bad Request)

```json
{
  "detail": "Validation failed",
  "errors": {
    "recipients": ["Invalid email address: invalid-email"],
    "day_of_week": ["Day of week is required for weekly schedules"]
  }
}
```

**UI Handling:**
- Display field-specific errors near form inputs
- Prevent form submission until resolved

#### Not Found (404)

```json
{
  "detail": "Schedule not found"
}
```

**UI Handling:**
- Show "Schedule not found" message
- Redirect to schedule list

#### Export Not Complete (400)

```json
{
  "detail": "Export is not complete"
}
```

**UI Handling:**
- Disable download button for non-completed exports
- Show status badge

#### File Not Available (404)

```json
{
  "detail": "Export file not available"
}
```

**UI Handling:**
- Show "File no longer available" message
- Suggest running export again

#### Server Error (500)

```json
{
  "detail": "Export failed: Database connection error"
}
```

**UI Handling:**
- Show generic error message
- Provide retry option
- Log to error tracking service

### Error Handling Best Practices

```javascript
const handleApiError = (error, context) => {
  // Network error
  if (!error.response) {
    return {
      title: 'Network Error',
      message: 'Unable to connect to server. Please check your internet connection.',
      action: 'retry'
    };
  }

  // Validation error
  if (error.response.status === 400) {
    return {
      title: 'Validation Error',
      message: error.response.data.detail || 'Please check your input',
      errors: error.response.data.errors,
      action: 'fix'
    };
  }

  // Unauthorized
  if (error.response.status === 401) {
    return {
      title: 'Authentication Required',
      message: 'Please log in again',
      action: 'login'
    };
  }

  // Not found
  if (error.response.status === 404) {
    return {
      title: 'Not Found',
      message: error.response.data.detail || `${context} not found`,
      action: 'back'
    };
  }

  // Server error
  return {
    title: 'Server Error',
    message: 'Something went wrong. Please try again later.',
    action: 'retry'
  };
};
```

---

## Best Practices

### 1. Timezone Handling

All times are in **UTC**. Display local times in the UI:

```javascript
// Convert UTC to local time for display
const displayLocalTime = (utcTimeString) => {
  const utcDate = new Date(utcTimeString);
  return utcDate.toLocaleString(); // Shows in user's timezone
};

// Show timezone info
const showTimezoneInfo = (hour) => {
  return `${hour}:00 UTC (${getLocalHour(hour)}:00 local)`;
};

const getLocalHour = (utcHour) => {
  const now = new Date();
  const utcDate = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), utcHour));
  return utcDate.getHours();
};
```

### 2. Pagination

Always use pagination for history:

```javascript
const fetchHistory = async (page = 1, pageSize = 20) => {
  const response = await fetch(
    `/reports/api/automation/history/?page=${page}&page_size=${pageSize}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  return await response.json();
};
```

### 3. Real-time Updates

Poll for status updates on pending/processing exports:

```javascript
const pollExportStatus = (historyId) => {
  const interval = setInterval(async () => {
    const response = await fetch(`/reports/api/automation/history/${historyId}/`);
    const history = await response.json();
    
    if (history.status === 'COMPLETED' || history.status === 'FAILED' || history.status === 'EMAILED') {
      clearInterval(interval);
      // Update UI with final status
      updateHistoryItem(history);
    }
  }, 5000); // Poll every 5 seconds
};
```

### 4. Optimistic UI Updates

Update UI immediately, then sync with server:

```javascript
const activateSchedule = async (scheduleId) => {
  // Optimistic update
  updateScheduleInUI(scheduleId, { is_active: true });
  
  try {
    const response = await fetch(
      `/reports/api/automation/schedules/${scheduleId}/activate/`,
      { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } }
    );
    
    if (!response.ok) throw new Error('Activation failed');
    
    const updated = await response.json();
    updateScheduleInUI(scheduleId, updated); // Sync with server
  } catch (error) {
    // Revert optimistic update
    updateScheduleInUI(scheduleId, { is_active: false });
    showError('Failed to activate schedule');
  }
};
```

### 5. File Download Progress

Show progress for large downloads:

```javascript
const downloadWithProgress = async (historyId, onProgress) => {
  const response = await fetch(`/reports/api/automation/history/${historyId}/download/`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const contentLength = response.headers.get('Content-Length');
  const total = parseInt(contentLength, 10);
  let loaded = 0;
  
  const reader = response.body.getReader();
  const chunks = [];
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    chunks.push(value);
    loaded += value.length;
    onProgress((loaded / total) * 100);
  }
  
  const blob = new Blob(chunks);
  // Trigger download
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = getFilenameFromResponse(response);
  a.click();
};
```

---

## Testing Guidance

### Manual Testing Checklist

**Schedules:**
- [ ] Create daily schedule
- [ ] Create weekly schedule (all days)
- [ ] Create monthly schedule (various days)
- [ ] Edit schedule (verify next_run_at updates)
- [ ] Delete schedule
- [ ] Activate/deactivate schedule
- [ ] Manually trigger schedule
- [ ] Test all 4 export types
- [ ] Test all 3 formats
- [ ] Verify email validation
- [ ] Test filter requirements

**History:**
- [ ] View paginated history
- [ ] Filter by export type
- [ ] Filter by format
- [ ] Filter by status
- [ ] Filter by date range
- [ ] Download completed export
- [ ] View error message for failed export
- [ ] Check statistics accuracy

**Notifications:**
- [ ] Get default settings
- [ ] Update settings
- [ ] Toggle success notifications
- [ ] Toggle failure notifications
- [ ] Add/remove recipients
- [ ] Validate email addresses

### API Testing Examples (Jest)

```javascript
describe('Export Automation API', () => {
  const API_BASE = '/api/reports/automation';
  const token = 'test-token';
  
  test('should create daily schedule', async () => {
    const scheduleData = {
      name: 'Test Daily Export',
      export_type: 'SALES',
      format: 'excel',
      frequency: 'DAILY',
      hour: 8,
      recipients: ['test@example.com'],
      filters: { start_date: '2024-01-01', end_date: '2024-12-31' },
      is_active: true
    };
    
    const response = await fetch(`${API_BASE}/schedules/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(scheduleData)
    });
    
    expect(response.status).toBe(201);
    const data = await response.json();
    expect(data.name).toBe('Test Daily Export');
    expect(data.next_run_at).toBeTruthy();
  });
  
  test('should validate weekly schedule requires day_of_week', async () => {
    const scheduleData = {
      name: 'Invalid Weekly',
      export_type: 'SALES',
      format: 'excel',
      frequency: 'WEEKLY',
      hour: 8,
      // Missing day_of_week
      recipients: ['test@example.com'],
      filters: { start_date: '2024-01-01', end_date: '2024-12-31' },
      is_active: true
    };
    
    const response = await fetch(`${API_BASE}/schedules/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(scheduleData)
    });
    
    expect(response.status).toBe(400);
    const error = await response.json();
    expect(error.errors.day_of_week).toBeTruthy();
  });
  
  test('should download export file', async () => {
    const historyId = 'test-history-id';
    
    const response = await fetch(`${API_BASE}/history/${historyId}/download/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toContain('application/');
    
    const blob = await response.blob();
    expect(blob.size).toBeGreaterThan(0);
  });
});
```

### Component Testing (React Testing Library)

```javascript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ScheduleForm from './ScheduleForm';

test('renders schedule form with all fields', () => {
  render(<ScheduleForm />);
  
  expect(screen.getByLabelText(/schedule name/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/export type/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/format/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/frequency/i)).toBeInTheDocument();
});

test('shows day_of_week selector when frequency is WEEKLY', async () => {
  render(<ScheduleForm />);
  
  const frequencySelect = screen.getByLabelText(/frequency/i);
  fireEvent.change(frequencySelect, { target: { value: 'WEEKLY' } });
  
  await waitFor(() => {
    expect(screen.getByLabelText(/day of week/i)).toBeInTheDocument();
  });
});

test('validates email addresses', async () => {
  const onSubmit = jest.fn();
  render(<ScheduleForm onSubmit={onSubmit} />);
  
  const emailInput = screen.getByLabelText(/recipients/i);
  fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
  
  const submitButton = screen.getByRole('button', { name: /create/i });
  fireEvent.click(submitButton);
  
  await waitFor(() => {
    expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
```

---

## Additional Resources

### TypeScript Interfaces

```typescript
// For TypeScript projects
export interface ExportSchedule {
  id: string;
  name: string;
  export_type: 'SALES' | 'CUSTOMERS' | 'INVENTORY' | 'AUDIT_LOGS';
  format: 'excel' | 'csv' | 'pdf';
  frequency: 'DAILY' | 'WEEKLY' | 'MONTHLY';
  hour: number;
  day_of_week: number | null;
  day_of_month: number | null;
  recipients: string[];
  include_creator_email: boolean;
  email_subject: string;
  email_message: string;
  filters: Record<string, any>;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  created_by_name: string;
  next_run_display: string;
  last_run_display: string;
  status_display: string;
}

export interface ExportHistory {
  id: string;
  export_type: string;
  format: string;
  trigger: 'MANUAL' | 'SCHEDULED' | 'API';
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'EMAILED';
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  file_name: string;
  file_size: number;
  file_path: string;
  record_count: number;
  filters_applied: Record<string, any>;
  email_sent: boolean;
  email_recipients: string[];
  email_sent_at: string | null;
  error_message: string | null;
  error_traceback: string | null;
  user: string;
  user_name: string;
  schedule: string | null;
  schedule_name: string | null;
  duration_display: string;
  file_size_display: string;
  status_display: string;
  duration_seconds: number;
  file_size_mb: number;
}

export interface ExportNotificationSettings {
  notify_on_success: boolean;
  notify_on_failure: boolean;
  default_recipients: string[];
  from_name: string;
  reply_to_email: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
```

### Postman Collection

Import this collection to test all endpoints:

```json
{
  "info": {
    "name": "Export Automation API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Schedules",
      "item": [
        {
          "name": "List Schedules",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer {{token}}"
              }
            ],
            "url": {
              "raw": "{{baseUrl}}/reports/api/automation/schedules/",
              "host": ["{{baseUrl}}"],
              "path": ["api", "reports", "automation", "schedules", ""]
            }
          }
        },
        {
          "name": "Create Schedule",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer {{token}}"
              },
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"name\": \"Daily Sales Export\",\n  \"export_type\": \"SALES\",\n  \"format\": \"excel\",\n  \"frequency\": \"DAILY\",\n  \"hour\": 8,\n  \"recipients\": [\"test@example.com\"],\n  \"include_creator_email\": true,\n  \"filters\": {\n    \"start_date\": \"2024-01-01\",\n    \"end_date\": \"2024-12-31\"\n  },\n  \"is_active\": true\n}"
            },
            "url": {
              "raw": "{{baseUrl}}/reports/api/automation/schedules/",
              "host": ["{{baseUrl}}"],
              "path": ["api", "reports", "automation", "schedules", ""]
            }
          }
        }
      ]
    }
  ]
}
```

---

## Support & Questions

**Backend Developer Contact:** [Your contact info]

**API Documentation:** This document

**Backend Repository:** [Repository URL]

**Issues & Bugs:** Create GitHub issue with `frontend` label

---

## Version History

- **v1.0** (2024-10-12) - Initial Phase 5 completion
  - All automation endpoints operational
  - Complete CRUD for schedules
  - Export history with download
  - Notification settings
  - Statistics dashboard data

---

**Status:** ✅ All APIs Ready for Frontend Integration  
**Last Updated:** October 12, 2024  
**Backend Phase:** 5 Complete
