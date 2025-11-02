# Tax Configuration API - Frontend Implementation Guide

## Overview

The POS Backend provides a complete tax management system for subscription payments. This guide covers all available API endpoints and data structures for implementing tax configuration in the frontend.

**Backend-First Architecture**: All tax calculations are performed on the backend. The frontend should NEVER implement tax calculation logic - it only displays what the backend provides.

---

## Table of Contents

1. [Tax Configuration Endpoints](#tax-configuration-endpoints)
2. [Data Models](#data-models)
3. [Common Use Cases](#common-use-cases)
4. [Frontend Implementation Examples](#frontend-implementation-examples)
5. [Error Handling](#error-handling)

---

## Tax Configuration Endpoints

### 1. List All Tax Configurations

**Endpoint**: `GET /subscriptions/api/tax-config/`

**Description**: Retrieve all tax configurations (with optional filtering)

**Query Parameters**:
- `is_active` (optional): Filter by active status (`true` or `false`)
- `country` (optional): Filter by country code (e.g., `GH` for Ghana)

**Example Request**:
```http
GET /subscriptions/api/tax-config/?is_active=true&country=GH
Authorization: Token <your-token>
```

**Example Response**:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Value Added Tax",
    "code": "VAT_GH",
    "description": "Ghana Value Added Tax",
    "rate": "15.00",
    "country": "GH",
    "applies_to_subscriptions": true,
    "is_mandatory": true,
    "calculation_order": 1,
    "applies_to": "SUBTOTAL",
    "is_active": true,
    "effective_from": "2024-01-01",
    "effective_until": null,
    "is_effective_now": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "National Health Insurance Levy",
    "code": "NHIL_GH",
    "description": "Ghana NHIL",
    "rate": "2.50",
    "country": "GH",
    "applies_to_subscriptions": true,
    "is_mandatory": true,
    "calculation_order": 2,
    "applies_to": "SUBTOTAL",
    "is_active": true,
    "effective_from": "2024-01-01",
    "effective_until": null,
    "is_effective_now": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

**Permissions**: Any authenticated user can view

---

### 2. Get Single Tax Configuration

**Endpoint**: `GET /subscriptions/api/tax-config/{id}/`

**Description**: Retrieve details of a specific tax configuration

**Example Request**:
```http
GET /subscriptions/api/tax-config/550e8400-e29b-41d4-a716-446655440000/
Authorization: Token <your-token>
```

**Example Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Value Added Tax",
  "code": "VAT_GH",
  "description": "Ghana Value Added Tax - Standard rate",
  "rate": "15.00",
  "country": "GH",
  "applies_to_subscriptions": true,
  "is_mandatory": true,
  "calculation_order": 1,
  "applies_to": "SUBTOTAL",
  "is_active": true,
  "effective_from": "2024-01-01",
  "effective_until": null,
  "is_effective_now": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Permissions**: Any authenticated user can view

---

### 3. Get Currently Active Taxes

**Endpoint**: `GET /subscriptions/api/tax-config/active/`

**Description**: Retrieve only taxes that are currently effective (considering `effective_from` and `effective_until` dates)

**Example Request**:
```http
GET /subscriptions/api/tax-config/active/
Authorization: Token <your-token>
```

**Example Response**:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Value Added Tax",
    "code": "VAT_GH",
    "rate": "15.00",
    "country": "GH",
    "applies_to_subscriptions": true,
    "is_mandatory": true,
    "calculation_order": 1,
    "applies_to": "SUBTOTAL",
    "is_active": true,
    "effective_from": "2024-01-01",
    "effective_until": null,
    "is_effective_now": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "National Health Insurance Levy",
    "code": "NHIL_GH",
    "rate": "2.50",
    "country": "GH",
    "applies_to_subscriptions": true,
    "is_mandatory": true,
    "calculation_order": 2,
    "applies_to": "SUBTOTAL",
    "is_active": true,
    "effective_from": "2024-01-01",
    "effective_until": null,
    "is_effective_now": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

**Permissions**: Any authenticated user can view

---

### 4. Create Tax Configuration (Admin Only)

**Endpoint**: `POST /subscriptions/api/tax-config/`

**Description**: Create a new tax configuration

**Request Body**:
```json
{
  "name": "New Tax",
  "code": "NEW_TAX_GH",
  "description": "Description of the new tax",
  "rate": "5.00",
  "country": "GH",
  "applies_to_subscriptions": true,
  "is_mandatory": true,
  "calculation_order": 3,
  "applies_to": "SUBTOTAL",
  "is_active": true,
  "effective_from": "2025-01-01",
  "effective_until": null
}
```

**Example Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "name": "New Tax",
  "code": "NEW_TAX_GH",
  "description": "Description of the new tax",
  "rate": "5.00",
  "country": "GH",
  "applies_to_subscriptions": true,
  "is_mandatory": true,
  "calculation_order": 3,
  "applies_to": "SUBTOTAL",
  "is_active": true,
  "effective_from": "2025-01-01",
  "effective_until": null,
  "is_effective_now": false,
  "created_at": "2024-11-02T10:00:00Z",
  "updated_at": "2024-11-02T10:00:00Z"
}
```

**Permissions**: Platform Admin only (`is_staff=True`)

**Status Codes**:
- `201 Created`: Tax configuration created successfully
- `400 Bad Request`: Invalid data
- `403 Forbidden`: User is not a platform admin
- `409 Conflict`: Tax code already exists

---

### 5. Update Tax Configuration (Admin Only)

**Endpoint**: `PUT /subscriptions/api/tax-config/{id}/` or `PATCH /subscriptions/api/tax-config/{id}/`

**Description**: Update an existing tax configuration

**Request Body** (full update with PUT):
```json
{
  "name": "Value Added Tax",
  "code": "VAT_GH",
  "description": "Updated VAT description",
  "rate": "17.50",
  "country": "GH",
  "applies_to_subscriptions": true,
  "is_mandatory": true,
  "calculation_order": 1,
  "applies_to": "SUBTOTAL",
  "is_active": true,
  "effective_from": "2025-04-01",
  "effective_until": null
}
```

**Request Body** (partial update with PATCH):
```json
{
  "rate": "17.50",
  "effective_from": "2025-04-01"
}
```

**Example Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Value Added Tax",
  "code": "VAT_GH",
  "description": "Updated VAT description",
  "rate": "17.50",
  "country": "GH",
  "applies_to_subscriptions": true,
  "is_mandatory": true,
  "calculation_order": 1,
  "applies_to": "SUBTOTAL",
  "is_active": true,
  "effective_from": "2025-04-01",
  "effective_until": null,
  "is_effective_now": false,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-11-02T10:30:00Z"
}
```

**Permissions**: Platform Admin only (`is_staff=True`)

**Status Codes**:
- `200 OK`: Tax configuration updated successfully
- `400 Bad Request`: Invalid data
- `403 Forbidden`: User is not a platform admin
- `404 Not Found`: Tax configuration not found

---

### 6. Delete Tax Configuration (Admin Only)

**Endpoint**: `DELETE /subscriptions/api/tax-config/{id}/`

**Description**: Delete a tax configuration

**Example Request**:
```http
DELETE /subscriptions/api/tax-config/550e8400-e29b-41d4-a716-446655440002/
Authorization: Token <your-token>
```

**Response**: `204 No Content` (successful deletion, no response body)

**Permissions**: Platform Admin only (`is_staff=True`)

**Status Codes**:
- `204 No Content`: Tax configuration deleted successfully
- `403 Forbidden`: User is not a platform admin
- `404 Not Found`: Tax configuration not found

---

## Data Models

### TaxConfiguration Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier |
| `name` | String | Display name (e.g., "Value Added Tax") |
| `code` | String | Unique code (e.g., "VAT_GH") |
| `description` | Text | Detailed description (optional) |
| `rate` | Decimal | Tax rate as percentage (e.g., 15.00 for 15%) |
| `country` | String | ISO 3166-1 alpha-2 country code (e.g., "GH") |
| `applies_to_subscriptions` | Boolean | Whether tax applies to subscriptions |
| `is_mandatory` | Boolean | Whether tax must be applied |
| `calculation_order` | Integer | Order in which tax is calculated (lower = first) |
| `applies_to` | String | "SUBTOTAL" or "CUMULATIVE" |
| `is_active` | Boolean | Whether tax is currently active |
| `effective_from` | Date | Date from which tax is effective |
| `effective_until` | Date | Date until which tax is effective (null = indefinite) |
| `is_effective_now` | Boolean | Computed: whether tax is effective today |
| `created_at` | DateTime | When tax was created |
| `updated_at` | DateTime | When tax was last updated |

### Field Details

**`applies_to` Options**:
- `SUBTOTAL`: Tax is calculated on the base amount before other taxes
- `CUMULATIVE`: Tax is calculated on the cumulative amount including previous taxes

**Ghana Default Taxes**:
The system comes with these pre-configured Ghana taxes:

1. **VAT (Value Added Tax)**: 15%
2. **NHIL (National Health Insurance Levy)**: 2.5%
3. **GETFund Levy**: 2.5%
4. **COVID-19 Health Recovery Levy**: 1%

All are calculated on SUBTOTAL (base amount).

---

## Common Use Cases

### Use Case 1: Display Active Taxes in Subscription Flow

**Goal**: Show users which taxes will be applied to their subscription

**Frontend Implementation**:

```typescript
// Fetch active taxes
async function getActiveTaxes() {
  const response = await fetch('/subscriptions/api/tax-config/active/', {
    headers: {
      'Authorization': `Token ${userToken}`
    }
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch taxes');
  }
  
  return await response.json();
}

// Display in UI
const taxes = await getActiveTaxes();

// Example: Display as a list
taxes.forEach(tax => {
  console.log(`${tax.name}: ${tax.rate}%`);
});
```

**Display Example**:
```
Applicable Taxes:
- Value Added Tax (VAT): 15.00%
- National Health Insurance Levy (NHIL): 2.50%
- GETFund Levy: 2.50%
- COVID-19 Health Recovery Levy: 1.00%
```

---

### Use Case 2: Admin Tax Management Dashboard

**Goal**: Allow platform admins to view, create, update, and delete tax configurations

**Frontend Implementation**:

```typescript
// Tax Management Component (Admin Only)

// 1. Fetch all taxes (including inactive)
async function getAllTaxes() {
  const response = await fetch('/subscriptions/api/tax-config/', {
    headers: {
      'Authorization': `Token ${adminToken}`
    }
  });
  return await response.json();
}

// 2. Create new tax
async function createTax(taxData) {
  const response = await fetch('/subscriptions/api/tax-config/', {
    method: 'POST',
    headers: {
      'Authorization': `Token ${adminToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(taxData)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create tax');
  }
  
  return await response.json();
}

// 3. Update tax rate
async function updateTaxRate(taxId, newRate, effectiveFrom) {
  const response = await fetch(`/subscriptions/api/tax-config/${taxId}/`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Token ${adminToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      rate: newRate,
      effective_from: effectiveFrom
    })
  });
  
  if (!response.ok) {
    throw new Error('Failed to update tax');
  }
  
  return await response.json();
}

// 4. Delete tax
async function deleteTax(taxId) {
  const response = await fetch(`/subscriptions/api/tax-config/${taxId}/`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Token ${adminToken}`
    }
  });
  
  if (!response.ok) {
    throw new Error('Failed to delete tax');
  }
}
```

---

### Use Case 3: Display Tax Breakdown in Payment Summary

**Goal**: Show detailed tax breakdown when user is about to pay for subscription

**Important**: DO NOT calculate taxes on the frontend! Use the pricing calculation endpoint.

**Endpoint**: `GET /subscriptions/api/pricing/calculate/`

**Query Parameters**:
- `storefronts` (required): Number of storefronts
- `gateway` (optional): Payment gateway (e.g., "PAYSTACK")

**Example Request**:
```http
GET /subscriptions/api/pricing/calculate/?storefronts=3&gateway=PAYSTACK
Authorization: Token <your-token>
```

**Example Response**:
```json
{
  "storefronts": 3,
  "currency": "GHS",
  "base_price": "180.00",
  "taxes": [
    {
      "code": "VAT_GH",
      "name": "Value Added Tax",
      "rate": 15.0,
      "amount": "27.00"
    },
    {
      "code": "NHIL_GH",
      "name": "National Health Insurance Levy",
      "rate": 2.5,
      "amount": "4.50"
    },
    {
      "code": "GETFUND_GH",
      "name": "GETFund Levy",
      "rate": 2.5,
      "amount": "4.50"
    },
    {
      "code": "COVID_GH",
      "name": "COVID-19 Health Recovery Levy",
      "rate": 1.0,
      "amount": "1.80"
    }
  ],
  "total_tax": "37.80",
  "service_charges": [
    {
      "code": "PAYSTACK_FEE",
      "name": "Payment Gateway Fee",
      "type": "PERCENTAGE",
      "rate": 2.0,
      "amount": "4.36"
    }
  ],
  "total_service_charges": "4.36",
  "total_amount": "222.16",
  "breakdown": {
    "tier_id": "550e8400-e29b-41d4-a716-446655440000",
    "tier_description": "1-5 storefronts: GHS 60.00 + 0.00/extra",
    "base_storefronts": 1,
    "additional_storefronts": 2,
    "price_per_additional": "60.00"
  }
}
```

**Frontend Display**:
```typescript
// Fetch pricing breakdown
async function getPricingBreakdown(storefronts: number, gateway: string = 'PAYSTACK') {
  const response = await fetch(
    `/subscriptions/api/pricing/calculate/?storefronts=${storefronts}&gateway=${gateway}`,
    {
      headers: {
        'Authorization': `Token ${userToken}`
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to calculate pricing');
  }
  
  return await response.json();
}

// Display in UI
const pricing = await getPricingBreakdown(3);

// Example rendering
console.log(`Base Price: ${pricing.currency} ${pricing.base_price}`);
console.log('Taxes:');
pricing.taxes.forEach(tax => {
  console.log(`  ${tax.name} (${tax.rate}%): ${pricing.currency} ${tax.amount}`);
});
console.log(`Total Tax: ${pricing.currency} ${pricing.total_tax}`);
console.log('Service Charges:');
pricing.service_charges.forEach(charge => {
  if (charge.type === 'PERCENTAGE') {
    console.log(`  ${charge.name} (${charge.rate}%): ${pricing.currency} ${charge.amount}`);
  } else {
    console.log(`  ${charge.name}: ${pricing.currency} ${charge.amount}`);
  }
});
console.log(`Total: ${pricing.currency} ${pricing.total_amount}`);
```

**UI Example**:
```
Subscription Payment Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Base Price (3 storefronts)    GHS 180.00

Taxes:
  VAT (15%)                    GHS  27.00
  NHIL (2.5%)                  GHS   4.50
  GETFund Levy (2.5%)          GHS   4.50
  COVID Levy (1%)              GHS   1.80
                              ─────────
  Total Tax                    GHS  37.80

Service Charges:
  Payment Gateway Fee (2%)     GHS   4.36
                              ─────────
  Total Charges                GHS   4.36

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL AMOUNT                   GHS 222.16
```

---

## Frontend Implementation Examples

### Example 1: React Component - Tax List (Read-only for Users)

```tsx
import React, { useEffect, useState } from 'react';

interface Tax {
  id: string;
  name: string;
  code: string;
  rate: string;
  country: string;
  is_active: boolean;
  is_effective_now: boolean;
}

export const TaxListComponent: React.FC = () => {
  const [taxes, setTaxes] = useState<Tax[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchActiveTaxes();
  }, []);

  const fetchActiveTaxes = async () => {
    try {
      const response = await fetch('/subscriptions/api/tax-config/active/', {
        headers: {
          'Authorization': `Token ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch taxes');
      }

      const data = await response.json();
      setTaxes(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading taxes...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="tax-list">
      <h2>Applicable Taxes</h2>
      <table>
        <thead>
          <tr>
            <th>Tax Name</th>
            <th>Code</th>
            <th>Rate</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {taxes.map(tax => (
            <tr key={tax.id}>
              <td>{tax.name}</td>
              <td>{tax.code}</td>
              <td>{tax.rate}%</td>
              <td>{tax.is_effective_now ? 'Active' : 'Inactive'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

---

### Example 2: React Component - Tax Management (Admin Only)

```tsx
import React, { useEffect, useState } from 'react';

interface TaxFormData {
  name: string;
  code: string;
  description: string;
  rate: string;
  country: string;
  applies_to_subscriptions: boolean;
  is_mandatory: boolean;
  calculation_order: number;
  applies_to: 'SUBTOTAL' | 'CUMULATIVE';
  is_active: boolean;
  effective_from: string;
  effective_until: string | null;
}

export const TaxManagementComponent: React.FC = () => {
  const [taxes, setTaxes] = useState<Tax[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [editingTax, setEditingTax] = useState<Tax | null>(null);
  const [formData, setFormData] = useState<TaxFormData>({
    name: '',
    code: '',
    description: '',
    rate: '',
    country: 'GH',
    applies_to_subscriptions: true,
    is_mandatory: true,
    calculation_order: 1,
    applies_to: 'SUBTOTAL',
    is_active: true,
    effective_from: new Date().toISOString().split('T')[0],
    effective_until: null
  });

  useEffect(() => {
    fetchAllTaxes();
  }, []);

  const fetchAllTaxes = async () => {
    const response = await fetch('/subscriptions/api/tax-config/', {
      headers: {
        'Authorization': `Token ${localStorage.getItem('adminToken')}`
      }
    });
    const data = await response.json();
    setTaxes(data);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const url = editingTax 
      ? `/subscriptions/api/tax-config/${editingTax.id}/`
      : '/subscriptions/api/tax-config/';
    
    const method = editingTax ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Token ${localStorage.getItem('adminToken')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(formData)
    });

    if (response.ok) {
      fetchAllTaxes(); // Refresh list
      resetForm();
    }
  };

  const handleEdit = (tax: Tax) => {
    setEditingTax(tax);
    setIsEditing(true);
    setFormData({
      name: tax.name,
      code: tax.code,
      description: tax.description,
      rate: tax.rate,
      country: tax.country,
      applies_to_subscriptions: tax.applies_to_subscriptions,
      is_mandatory: tax.is_mandatory,
      calculation_order: tax.calculation_order,
      applies_to: tax.applies_to,
      is_active: tax.is_active,
      effective_from: tax.effective_from,
      effective_until: tax.effective_until
    });
  };

  const handleDelete = async (taxId: string) => {
    if (!confirm('Are you sure you want to delete this tax?')) return;

    const response = await fetch(`/subscriptions/api/tax-config/${taxId}/`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Token ${localStorage.getItem('adminToken')}`
      }
    });

    if (response.ok) {
      fetchAllTaxes(); // Refresh list
    }
  };

  const resetForm = () => {
    setEditingTax(null);
    setIsEditing(false);
    setFormData({
      name: '',
      code: '',
      description: '',
      rate: '',
      country: 'GH',
      applies_to_subscriptions: true,
      is_mandatory: true,
      calculation_order: 1,
      applies_to: 'SUBTOTAL',
      is_active: true,
      effective_from: new Date().toISOString().split('T')[0],
      effective_until: null
    });
  };

  return (
    <div className="tax-management">
      <h1>Tax Configuration Management</h1>
      
      {/* Tax Form */}
      <form onSubmit={handleSubmit}>
        <h2>{isEditing ? 'Edit Tax' : 'Create New Tax'}</h2>
        
        <div>
          <label>Name:</label>
          <input
            type="text"
            value={formData.name}
            onChange={e => setFormData({...formData, name: e.target.value})}
            required
          />
        </div>

        <div>
          <label>Code:</label>
          <input
            type="text"
            value={formData.code}
            onChange={e => setFormData({...formData, code: e.target.value})}
            required
          />
        </div>

        <div>
          <label>Rate (%):</label>
          <input
            type="number"
            step="0.01"
            value={formData.rate}
            onChange={e => setFormData({...formData, rate: e.target.value})}
            required
          />
        </div>

        <div>
          <label>Effective From:</label>
          <input
            type="date"
            value={formData.effective_from}
            onChange={e => setFormData({...formData, effective_from: e.target.value})}
            required
          />
        </div>

        <div>
          <label>
            <input
              type="checkbox"
              checked={formData.is_active}
              onChange={e => setFormData({...formData, is_active: e.target.checked})}
            />
            Active
          </label>
        </div>

        <button type="submit">{isEditing ? 'Update' : 'Create'}</button>
        {isEditing && <button type="button" onClick={resetForm}>Cancel</button>}
      </form>

      {/* Tax List */}
      <h2>Existing Taxes</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Code</th>
            <th>Rate</th>
            <th>Status</th>
            <th>Effective From</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {taxes.map(tax => (
            <tr key={tax.id}>
              <td>{tax.name}</td>
              <td>{tax.code}</td>
              <td>{tax.rate}%</td>
              <td>{tax.is_active ? 'Active' : 'Inactive'}</td>
              <td>{tax.effective_from}</td>
              <td>
                <button onClick={() => handleEdit(tax)}>Edit</button>
                <button onClick={() => handleDelete(tax.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

---

### Example 3: Payment Breakdown Component

```tsx
import React, { useEffect, useState } from 'react';

interface PricingBreakdown {
  storefronts: number;
  currency: string;
  base_price: string;
  taxes: Array<{
    code: string;
    name: string;
    rate: number;
    amount: string;
  }>;
  total_tax: string;
  service_charges: Array<{
    code: string;
    name: string;
    type: string;
    rate?: number;
    amount: string;
  }>;
  total_service_charges: string;
  total_amount: string;
}

export const PaymentBreakdownComponent: React.FC<{ storefronts: number }> = ({ storefronts }) => {
  const [breakdown, setBreakdown] = useState<PricingBreakdown | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPricingBreakdown();
  }, [storefronts]);

  const fetchPricingBreakdown = async () => {
    try {
      const response = await fetch(
        `/subscriptions/api/pricing/calculate/?storefronts=${storefronts}&gateway=PAYSTACK`,
        {
          headers: {
            'Authorization': `Token ${localStorage.getItem('token')}`
          }
        }
      );

      const data = await response.json();
      setBreakdown(data);
    } catch (error) {
      console.error('Failed to fetch pricing:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !breakdown) return <div>Calculating pricing...</div>;

  return (
    <div className="payment-breakdown">
      <h3>Payment Summary</h3>
      
      <div className="breakdown-section">
        <div className="line-item">
          <span>Base Price ({breakdown.storefronts} storefronts)</span>
          <span>{breakdown.currency} {breakdown.base_price}</span>
        </div>
      </div>

      <div className="breakdown-section">
        <h4>Taxes</h4>
        {breakdown.taxes.map(tax => (
          <div key={tax.code} className="line-item indent">
            <span>{tax.name} ({tax.rate}%)</span>
            <span>{breakdown.currency} {tax.amount}</span>
          </div>
        ))}
        <div className="line-item subtotal">
          <span>Total Tax</span>
          <span>{breakdown.currency} {breakdown.total_tax}</span>
        </div>
      </div>

      {breakdown.service_charges.length > 0 && (
        <div className="breakdown-section">
          <h4>Service Charges</h4>
          {breakdown.service_charges.map(charge => (
            <div key={charge.code} className="line-item indent">
              <span>
                {charge.name}
                {charge.type === 'PERCENTAGE' && ` (${charge.rate}%)`}
              </span>
              <span>{breakdown.currency} {charge.amount}</span>
            </div>
          ))}
          <div className="line-item subtotal">
            <span>Total Charges</span>
            <span>{breakdown.currency} {breakdown.total_service_charges}</span>
          </div>
        </div>
      )}

      <div className="breakdown-section total">
        <div className="line-item">
          <span><strong>TOTAL AMOUNT</strong></span>
          <span><strong>{breakdown.currency} {breakdown.total_amount}</strong></span>
        </div>
      </div>
    </div>
  );
};
```

---

## Error Handling

### Common Error Responses

**400 Bad Request - Invalid Data**:
```json
{
  "rate": ["Ensure this value is greater than or equal to 0."],
  "code": ["Tax configuration with this code already exists."]
}
```

**403 Forbidden - Permission Denied**:
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**404 Not Found**:
```json
{
  "detail": "Not found."
}
```

**500 Internal Server Error**:
```json
{
  "error": "Internal server error",
  "detail": "An unexpected error occurred"
}
```

### Error Handling Example

```typescript
async function handleTaxOperation<T>(operation: () => Promise<T>): Promise<T> {
  try {
    return await operation();
  } catch (error) {
    if (error.response) {
      switch (error.response.status) {
        case 400:
          const validationErrors = await error.response.json();
          throw new Error(`Validation failed: ${JSON.stringify(validationErrors)}`);
        
        case 403:
          throw new Error('You do not have permission to perform this action');
        
        case 404:
          throw new Error('Tax configuration not found');
        
        case 500:
          throw new Error('Server error occurred. Please try again later');
        
        default:
          throw new Error(`Unexpected error: ${error.response.status}`);
      }
    }
    throw error;
  }
}

// Usage
try {
  const taxes = await handleTaxOperation(() => 
    fetch('/subscriptions/api/tax-config/').then(r => r.json())
  );
  console.log('Taxes loaded:', taxes);
} catch (error) {
  console.error('Failed to load taxes:', error.message);
  // Display user-friendly error message
}
```

---

## Best Practices

### 1. Never Calculate Taxes on Frontend
❌ **DON'T DO THIS**:
```typescript
// WRONG - Don't calculate taxes on frontend!
const calculateTax = (amount: number, rate: number) => {
  return amount * (rate / 100);
};
```

✅ **DO THIS INSTEAD**:
```typescript
// Correct - Always get calculations from backend
const pricing = await fetch('/subscriptions/api/pricing/calculate/?storefronts=3')
  .then(r => r.json());

console.log('Total tax:', pricing.total_tax); // Backend calculated
```

### 2. Cache Active Taxes
```typescript
// Cache taxes for better performance
let cachedTaxes: Tax[] | null = null;
let cacheTimestamp: number | null = null;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

async function getActiveTaxes(forceRefresh = false): Promise<Tax[]> {
  const now = Date.now();
  
  if (!forceRefresh && cachedTaxes && cacheTimestamp && 
      (now - cacheTimestamp) < CACHE_DURATION) {
    return cachedTaxes;
  }

  const response = await fetch('/subscriptions/api/tax-config/active/');
  const taxes = await response.json();
  
  cachedTaxes = taxes;
  cacheTimestamp = now;
  
  return taxes;
}
```

### 3. Display Tax Information Clearly
- Always show tax breakdown before payment
- Display individual tax amounts, not just total
- Show tax names and rates
- Make it clear what the user is paying for

### 4. Admin Permissions Check
```typescript
// Check if user is admin before showing admin features
const isAdmin = user.is_staff || user.role === 'SUPER_ADMIN';

if (isAdmin) {
  // Show tax management features
} else {
  // Show read-only tax information
}
```

---

## Summary

### Key Takeaways for Frontend Developers

1. **All tax configurations are managed via REST API**
2. **Platform admins can create/update/delete taxes**
3. **Regular users can only view active taxes**
4. **Never implement tax calculation on frontend** - always use `/subscriptions/api/pricing/calculate/`
5. **Tax breakdown is automatically included in payment initialization**
6. **All tax amounts are stored in payment records for audit trail**

### Base API URL Structure
```
/subscriptions/api/
├── tax-config/                    # Tax CRUD operations
│   ├── {id}/                      # Get/Update/Delete specific tax
│   └── active/                    # Get currently effective taxes
└── pricing/calculate/             # Calculate complete pricing with taxes
```

### Required Headers
```http
Authorization: Token <user-token-here>
Content-Type: application/json
```

---

## Support

For questions or issues:
- Backend Developer: Check `subscriptions/models.py` and `subscriptions/views.py`
- API Documentation: This file
- Test Data: Run `python manage.py setup_default_pricing` to create Ghana default taxes

---

**Last Updated**: November 2, 2025
**API Version**: v1
**Backend Location**: `/subscriptions/` Django app
