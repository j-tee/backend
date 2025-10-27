# Credit Management and Payment Tracking - Complete Guide

## Overview
Comprehensive credit sales management system with payment tracking, status management, and financial reporting for the POS backend.

## Implementation Date
2025-01-07

---

## Table of Contents
1. [Credit Sales Flow](#credit-sales-flow)
2. [Sale Status States](#sale-status-states)
3. [API Endpoints](#api-endpoints)
4. [Payment Recording](#payment-recording)
5. [Credit Filters](#credit-filters)
6. [Financial Summaries](#financial-summaries)
7. [Frontend Integration Examples](#frontend-integration-examples)
8. [Business Rules](#business-rules)
9. [Error Handling](#error-handling)
10. [Testing](#testing)

---

## 1. Credit Sales Flow

### Complete Credit Sale Lifecycle

```
┌─────────────┐
│   Create    │
│  Sale (DRAFT)│
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Add Items to    │
│ Cart (DRAFT)    │
└──────┬──────────┘
       │
       ▼
┌──────────────────────┐
│ Complete Sale with   │
│ payment_type=CREDIT  │
└──────┬───────────────┘
       │
       ├─── No Payment ──────► PENDING (amount_due = total_amount)
       │
       ├─── Partial Payment ─► PARTIAL (amount_due > 0, amount_paid > 0)
       │
       └─── Full Payment ────► COMPLETED (amount_due = 0)
       
       
PENDING/PARTIAL Sales:
       │
       ▼
┌──────────────────┐
│ Record Payment   │
│ (Any amount)     │
└──────┬───────────┘
       │
       ├─── Still owes money ──► Remains PARTIAL
       │
       └─── Paid in full ──────► Changes to COMPLETED
```

### Sale Creation Flow
1. **Create Sale**: POST `/api/sales/` with `payment_type=CREDIT`
2. **Add Items**: POST `/api/sales/{id}/add_item/` for each product
3. **Complete Sale**: POST `/api/sales/{id}/complete_sale/`
   - If no initial payment: Status = PENDING
   - If partial payment: Status = PARTIAL
   - If full payment: Status = COMPLETED

---

## 2. Sale Status States

### Status Definitions

| Status | Description | amount_paid | amount_due | Can Record Payment? |
|--------|-------------|-------------|------------|---------------------|
| **DRAFT** | Sale in progress (cart) | 0 | 0 | No |
| **PENDING** | Credit sale, no payment received | 0 | = total_amount | Yes |
| **PARTIAL** | Credit sale, partial payment made | > 0 | > 0 | Yes |
| **COMPLETED** | Fully paid (cash or credit) | = total_amount | 0 | No |
| **REFUNDED** | Sale was refunded | N/A | N/A | No |
| **CANCELLED** | Sale was cancelled | 0 | 0 | No |

### Status Transitions

```
DRAFT ──complete_sale()──► PENDING  (credit, no payment)
                         │
                         ├──► PARTIAL  (credit, partial payment)
                         │
                         └──► COMPLETED (credit, full payment)

PENDING ──record_payment()──► PARTIAL   (partial payment)
                            │
                            └──► COMPLETED (full payment)

PARTIAL ──record_payment()──► COMPLETED (remaining payment)
```

---

## 3. API Endpoints

### 3.1 Create Credit Sale

**Endpoint:** `POST /api/sales/`

**Request Body:**
```json
{
  "customer": "uuid-of-customer",  // REQUIRED for credit sales
  "payment_type": "CREDIT",
  "storefront": "uuid-of-storefront"
}
```

**Response:** `201 Created`
```json
{
  "id": "sale-uuid",
  "receipt_number": null,
  "status": "DRAFT",
  "payment_type": "CREDIT",
  "customer": "customer-uuid",
  "subtotal": "0.00",
  "total_amount": "0.00",
  "amount_paid": "0.00",
  "amount_due": "0.00",
  "payment_status": "unpaid",
  "payment_completion_percentage": 0,
  "sale_items": []
}
```

### 3.2 Add Items to Sale

**Endpoint:** `POST /api/sales/{sale_id}/add_item/`

**Request Body:**
```json
{
  "product": "product-uuid",
  "stock_product": "stock-product-uuid",  // Optional but recommended
  "quantity": 2,
  "unit_price": "100.00",
  "discount_percentage": "0.00",  // Optional
  "tax_rate": "0.00"  // Optional
}
```

**Response:** `200 OK`
```json
{
  "id": "sale-uuid",
  "subtotal": "200.00",
  "total_amount": "200.00",
  "sale_items": [
    {
      "id": "item-uuid",
      "product": "product-uuid",
      "product_name": "Product Name",
      "quantity": 2,
      "unit_price": "100.00",
      "total_price": "200.00"
    }
  ]
}
```

### 3.3 Complete Credit Sale

**Endpoint:** `POST /api/sales/{sale_id}/complete_sale/`

**Request Body (No Initial Payment):**
```json
{
  "payment_method": "CREDIT"
}
```

**Request Body (With Initial Payment):**
```json
{
  "payment_method": "CREDIT",
  "amount_paid": "50.00"  // Partial payment
}
```

**Response:** `200 OK`
```json
{
  "id": "sale-uuid",
  "receipt_number": "INV-2025-00123",
  "status": "PENDING",  // or "PARTIAL" if amount_paid > 0
  "payment_type": "CREDIT",
  "customer": {
    "id": "customer-uuid",
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890"
  },
  "total_amount": "200.00",
  "amount_paid": "0.00",  // or "50.00" if partial payment
  "amount_due": "200.00",  // or "150.00" if partial payment
  "payment_status": "unpaid",  // or "partial"
  "payment_completion_percentage": 0,  // or 25
  "completed_at": "2025-01-07T10:30:00Z",
  "sale_items": [...]
}
```

### 3.4 Record Payment

**Endpoint:** `POST /api/sales/{sale_id}/record_payment/`

**Request Body:**
```json
{
  "amount": "75.00",
  "payment_method": "CASH",  // or "CARD", "MOBILE", "BANK_TRANSFER"
  "reference_number": "TXN-12345",  // Optional
  "notes": "Second payment installment"  // Optional
}
```

**Response:** `200 OK`
```json
{
  "message": "Payment of $75.00 recorded successfully",
  "sale": {
    "id": "sale-uuid",
    "receipt_number": "INV-2025-00123",
    "status": "PARTIAL",  // or "COMPLETED" if fully paid
    "total_amount": "200.00",
    "amount_paid": "125.00",  // Previous + new payment
    "amount_due": "75.00",  // Remaining balance
    "payment_status": "partial",  // or "paid"
    "payment_completion_percentage": 62.5
  },
  "payment": {
    "id": "payment-uuid",
    "amount": "75.00",
    "payment_method": "CASH",
    "reference_number": "TXN-12345",
    "created_at": "2025-01-07T14:45:00Z",
    "notes": "Second payment installment"
  }
}
```

**Error Response:** `400 Bad Request`
```json
{
  "error": "Payment amount ($250.00) exceeds outstanding balance ($75.00)"
}
```

---

## 4. Payment Recording

### 4.1 Recording a Payment

**Rules:**
- Can only record payments for PENDING or PARTIAL sales
- Payment amount must be > 0
- Payment amount cannot exceed `amount_due`
- Payment creates a Payment record linked to the sale
- Updates customer's balance (if customer exists)

**What Happens:**
1. Validates sale status (must be PENDING or PARTIAL)
2. Validates payment amount (> 0 and <= amount_due)
3. Creates Payment record
4. Updates sale's `amount_paid` and `amount_due`
5. Updates sale status (PARTIAL → COMPLETED if fully paid)
6. Updates customer's balance
7. Creates audit log entry

### 4.2 Payment Methods

```python
PAYMENT_METHOD_CHOICES = [
    ('CASH', 'Cash'),
    ('CARD', 'Card'),
    ('MOBILE', 'Mobile Money'),
    ('BANK_TRANSFER', 'Bank Transfer'),
    ('CHECK', 'Check'),
    ('OTHER', 'Other')
]
```

### 4.3 Payment History

**Endpoint:** `GET /api/sales/{sale_id}/payments/`

**Response:** `200 OK`
```json
{
  "count": 3,
  "results": [
    {
      "id": "payment-uuid-1",
      "amount": "50.00",
      "payment_method": "CASH",
      "reference_number": "TXN-001",
      "created_at": "2025-01-07T10:30:00Z",
      "created_by": {
        "id": "user-uuid",
        "email": "cashier@example.com"
      },
      "notes": "Initial deposit"
    },
    {
      "id": "payment-uuid-2",
      "amount": "75.00",
      "payment_method": "MOBILE",
      "reference_number": "MPESA-12345",
      "created_at": "2025-01-08T15:20:00Z",
      "created_by": {...},
      "notes": "M-Pesa payment"
    },
    {
      "id": "payment-uuid-3",
      "amount": "75.00",
      "payment_method": "CARD",
      "reference_number": "CARD-789",
      "created_at": "2025-01-09T09:10:00Z",
      "created_by": {...},
      "notes": "Final payment"
    }
  ]
}
```

---

## 5. Credit Filters

### 5.1 Available Filters

**Endpoint:** `GET /api/sales/`

| Filter Parameter | Type | Description | Example |
|-----------------|------|-------------|---------|
| `status` | String | Filter by sale status | `?status=PENDING` |
| `payment_type` | String | Filter by payment type | `?payment_type=CREDIT` |
| `has_outstanding_balance` | Boolean | Sales with unpaid balance | `?has_outstanding_balance=true` |
| `payment_status` | String | Payment status (unpaid/partial/paid) | `?payment_status=unpaid` |
| `days_outstanding` | Integer | Days since sale completed | `?days_outstanding=30` |
| `min_amount_due` | Decimal | Minimum amount owed | `?min_amount_due=1000` |
| `max_amount_due` | Decimal | Maximum amount owed | `?max_amount_due=5000` |
| `customer_id` | UUID | Filter by customer | `?customer_id=uuid` |

### 5.2 Filter Examples

**Unpaid Credit Sales:**
```
GET /api/sales/?payment_type=CREDIT&payment_status=unpaid
```

**Partially Paid Sales:**
```
GET /api/sales/?payment_type=CREDIT&payment_status=partial
```

**All Sales with Outstanding Balance:**
```
GET /api/sales/?has_outstanding_balance=true
```

**Overdue Credit Sales (> 30 days):**
```
GET /api/sales/?payment_type=CREDIT&days_outstanding=30&has_outstanding_balance=true
```

**High-Value Outstanding Sales:**
```
GET /api/sales/?has_outstanding_balance=true&min_amount_due=5000
```

**Customer's Credit Sales:**
```
GET /api/sales/?customer_id=customer-uuid&payment_type=CREDIT
```

**Combined Filters:**
```
GET /api/sales/?payment_type=CREDIT&payment_status=partial&min_amount_due=100&max_amount_due=1000
```

### 5.3 Filter Response

```json
{
  "count": 25,
  "next": "http://api.example.com/api/sales/?page=2&payment_type=CREDIT",
  "previous": null,
  "results": [
    {
      "id": "sale-uuid",
      "receipt_number": "INV-2025-00123",
      "status": "PENDING",
      "payment_type": "CREDIT",
      "customer": {
        "id": "customer-uuid",
        "name": "John Doe",
        "email": "john@example.com"
      },
      "total_amount": "1500.00",
      "amount_paid": "0.00",
      "amount_due": "1500.00",
      "payment_status": "unpaid",
      "payment_completion_percentage": 0,
      "completed_at": "2024-12-15T10:30:00Z",
      "created_at": "2024-12-15T10:15:00Z"
    }
  ]
}
```

---

## 6. Financial Summaries

### 6.1 Summary Endpoint

**Endpoint:** `GET /api/sales/summary/`

**Response:** `200 OK`
```json
{
  // Revenue Metrics (Accrual Basis)
  "total_sales": "992411.28",
  "total_refunds": "12500.00",
  "net_sales": "979911.28",
  "total_transactions": 510,
  "completed_transactions": 375,
  "avg_transaction": "2645.63",
  
  // Cash Accounting (Revenue-Based)
  "cash_at_hand": "996864.85",  // Total amount_paid
  "accounts_receivable": "156254.48",  // Total amount_due for CREDIT PENDING/PARTIAL
  
  // Profit Accounting (NEW - PROPORTIONAL CALCULATION)
  "total_profit": "450000.00",  // Profit from all COMPLETED sales
  "outstanding_credit": "55000.00",  // Profit from UNPAID portion of credit sales (proportional)
  "realized_credit_profit": "25000.00",  // NEW: Profit from PAID portion of credit sales
  "cash_on_hand": "395000.00",  // total_profit - outstanding_credit
  "total_credit_sales": "156254.48",  // Same as accounts_receivable
  "unpaid_credit_count": 25,  // Number of PENDING/PARTIAL credit sales
  
  // Financial Position
  "financial_position": {
    "cash_at_hand": "996864.85",
    "accounts_receivable": "156254.48",
    "total_assets": "1153119.33",
    "cash_percentage": 86.45,
    "receivables_percentage": 13.55
  },
  
  // Credit Health Metrics
  "credit_health": {
    "total_credit_sales": "350000.00",  // All credit sales (COMPLETED included)
    "unpaid_amount": "85000.00",  // PENDING credit sales
    "partially_paid_amount": "71254.48",  // PARTIAL credit sales
    "fully_paid_amount": "193745.52",  // COMPLETED credit sales
    "collection_rate": 55.36  // Percentage of credit sales fully paid
  },
  
  // Payment Method Breakdown
  "cash_sales": "550000.00",
  "card_sales": "220000.00",
  "credit_sales_total": "193745.52",  // Only COMPLETED credit sales
  "mobile_sales": "28665.76",
  
  // Status Breakdown
  "status_breakdown": [
    {"status": "COMPLETED", "count": 375, "total": "979911.28"},
    {"status": "PENDING", "count": 15, "total": "85000.00"},
    {"status": "PARTIAL", "count": 10, "total": "71254.48"},
    {"status": "DRAFT", "count": 23, "total": "0.00"}
  ]
}
```

### 6.2 Key Metrics Explained

**Revenue vs Profit:**
- `total_sales`: Total revenue from all completed sales
- `total_profit`: Total profit (revenue - costs) from completed sales
- Profit margin: `total_profit / total_sales × 100`

**Cash vs Accrual:**
- `cash_at_hand` (revenue): Actual cash received (`amount_paid`)
- `accounts_receivable`: Money customers owe (`amount_due`)
- `total_assets`: `cash_at_hand + accounts_receivable`

**Profit-Based Cash (PROPORTIONAL CALCULATION):**
- `cash_on_hand` (profit): Realized profit including partial credit payments
- `outstanding_credit`: Profit from UNPAID portion only (proportional to amount_due)
- `realized_credit_profit`: Profit from PAID portion (proportional to amount_paid)
- Shows true financial position

**How Proportional Calculation Works:**

For PARTIAL credit sales, profit is split based on payment percentage:

**Example:**
- Credit sale: $1,000 (with $300 profit)
- Customer paid: $400 (40%)
- Outstanding: $600 (60%)

**Calculation:**
- Outstanding Profit = $300 × 60% = **$180** (still in accounts receivable)
- Realized Profit = $300 × 40% = **$120** (already in cash on hand)

**Benefits:**
- ✅ Accurately reflects profit already collected from partial payments
- ✅ Outstanding credit decreases as customers make payments
- ✅ Cash on hand increases with each payment automatically
- ✅ Aligns with revenue-based cash_at_hand calculation

**Credit Health:**
- `collection_rate`: Percentage of credit sales fully collected
- Higher = better cash flow
- Lower = more outstanding debt

### 6.3 Proportional Profit Deep Dive

The proportional profit calculation ensures that when customers make payments against credit sales, the financial metrics accurately reflect the business's true position.

**Scenario Comparison:**

**Scenario 1: Fully Unpaid (PENDING)**
```
Sale: $1,000 | Profit: $300 | Paid: $0 | Due: $1,000
Outstanding Profit: $300 × 100% = $300.00
Realized Profit: $300 × 0% = $0.00
```

**Scenario 2: 40% Paid (PARTIAL)**
```
Sale: $1,000 | Profit: $300 | Paid: $400 | Due: $600
Outstanding Profit: $300 × 60% = $180.00
Realized Profit: $300 × 40% = $120.00
✅ $120 now included in cash on hand
```

**Scenario 3: 75% Paid (PARTIAL)**
```
Sale: $2,000 | Profit: $600 | Paid: $1,500 | Due: $500
Outstanding Profit: $600 × 25% = $150.00
Realized Profit: $600 × 75% = $450.00
✅ $450 now included in cash on hand
```

**Scenario 4: Fully Paid (COMPLETED)**
```
Sale: $1,000 | Profit: $300 | Paid: $1,000 | Due: $0
Outstanding Profit: $300 × 0% = $0.00
Realized Profit: $300 × 100% = $300.00
✅ All $300 in cash on hand
```

**Overall Impact:**
When a business has multiple partial payments, the proportional calculation can significantly increase the reported cash on hand. For example, with the scenarios above:

- **Old Approach** (all-or-nothing): Cash on Hand = $300 (only fully paid sales)
- **New Approach** (proportional): Cash on Hand = $870 ($0 + $120 + $450 + $300)
- **Difference**: +$570 recognized from partial payments

**This gives business owners a more accurate view of their available profit.**

---

## 7. Frontend Integration Examples

### 7.1 React/TypeScript Example

```typescript
// types.ts
interface Sale {
  id: string;
  receipt_number: string;
  status: 'DRAFT' | 'PENDING' | 'PARTIAL' | 'COMPLETED' | 'REFUNDED' | 'CANCELLED';
  payment_type: 'CASH' | 'CARD' | 'CREDIT' | 'MOBILE';
  customer?: {
    id: string;
    name: string;
    email: string;
  };
  total_amount: string;
  amount_paid: string;
  amount_due: string;
  payment_status: 'unpaid' | 'partial' | 'paid';
  payment_completion_percentage: number;
  completed_at: string;
  sale_items: SaleItem[];
}

interface RecordPaymentRequest {
  amount: string;
  payment_method: 'CASH' | 'CARD' | 'MOBILE' | 'BANK_TRANSFER' | 'CHECK' | 'OTHER';
  reference_number?: string;
  notes?: string;
}

// api.ts
export const creditSalesAPI = {
  // Get unpaid credit sales
  getUnpaidCreditSales: async (): Promise<Sale[]> => {
    const response = await fetch(
      '/api/sales/?payment_type=CREDIT&payment_status=unpaid'
    );
    const data = await response.json();
    return data.results;
  },

  // Get partially paid credit sales
  getPartiallyPaidSales: async (): Promise<Sale[]> => {
    const response = await fetch(
      '/api/sales/?payment_type=CREDIT&payment_status=partial'
    );
    const data = await response.json();
    return data.results;
  },

  // Get overdue credit sales (> 30 days)
  getOverdueSales: async (days: number = 30): Promise<Sale[]> => {
    const response = await fetch(
      `/api/sales/?payment_type=CREDIT&days_outstanding=${days}&has_outstanding_balance=true`
    );
    const data = await response.json();
    return data.results;
  },

  // Get customer's credit sales
  getCustomerCreditSales: async (customerId: string): Promise<Sale[]> => {
    const response = await fetch(
      `/api/sales/?customer_id=${customerId}&payment_type=CREDIT`
    );
    const data = await response.json();
    return data.results;
  },

  // Record payment for a sale
  recordPayment: async (
    saleId: string,
    paymentData: RecordPaymentRequest
  ): Promise<any> => {
    const response = await fetch(`/api/sales/${saleId}/record_payment/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(paymentData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to record payment');
    }

    return response.json();
  },

  // Get payment history for a sale
  getPaymentHistory: async (saleId: string): Promise<Payment[]> => {
    const response = await fetch(`/api/sales/${saleId}/payments/`);
    const data = await response.json();
    return data.results;
  },

  // Get financial summary
  getSummary: async (): Promise<FinancialSummary> => {
    const response = await fetch('/api/sales/summary/');
    return response.json();
  },
};

// components/RecordPaymentDialog.tsx
import React, { useState } from 'react';

interface RecordPaymentDialogProps {
  sale: Sale;
  onClose: () => void;
  onSuccess: () => void;
}

export const RecordPaymentDialog: React.FC<RecordPaymentDialogProps> = ({
  sale,
  onClose,
  onSuccess,
}) => {
  const [amount, setAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<RecordPaymentRequest['payment_method']>('CASH');
  const [referenceNumber, setReferenceNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await creditSalesAPI.recordPayment(sale.id, {
        amount,
        payment_method: paymentMethod,
        reference_number: referenceNumber || undefined,
        notes: notes || undefined,
      });

      onSuccess();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const maxAmount = parseFloat(sale.amount_due);
  const amountValue = parseFloat(amount) || 0;

  return (
    <div className="dialog">
      <h2>Record Payment</h2>
      
      <div className="sale-info">
        <p><strong>Receipt:</strong> {sale.receipt_number}</p>
        <p><strong>Customer:</strong> {sale.customer?.name}</p>
        <p><strong>Total:</strong> ${sale.total_amount}</p>
        <p><strong>Paid:</strong> ${sale.amount_paid}</p>
        <p><strong>Outstanding:</strong> ${sale.amount_due}</p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Payment Amount *</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            max={maxAmount}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
          <small>Maximum: ${sale.amount_due}</small>
        </div>

        <div className="form-group">
          <label>Payment Method *</label>
          <select
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value as any)}
            required
          >
            <option value="CASH">Cash</option>
            <option value="CARD">Card</option>
            <option value="MOBILE">Mobile Money</option>
            <option value="BANK_TRANSFER">Bank Transfer</option>
            <option value="CHECK">Check</option>
            <option value="OTHER">Other</option>
          </select>
        </div>

        <div className="form-group">
          <label>Reference Number</label>
          <input
            type="text"
            value={referenceNumber}
            onChange={(e) => setReferenceNumber(e.target.value)}
            placeholder="Transaction ID, Check #, etc."
          />
        </div>

        <div className="form-group">
          <label>Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Additional notes..."
          />
        </div>

        {error && <div className="error">{error}</div>}

        <div className="actions">
          <button type="button" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button type="submit" disabled={loading || amountValue === 0}>
            {loading ? 'Recording...' : `Record Payment ($${amount || '0.00'})`}
          </button>
        </div>
      </form>
    </div>
  );
};

// components/CreditSalesList.tsx
export const CreditSalesList: React.FC = () => {
  const [sales, setSales] = useState<Sale[]>([]);
  const [filter, setFilter] = useState<'all' | 'unpaid' | 'partial' | 'overdue'>('all');
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);

  useEffect(() => {
    loadSales();
  }, [filter]);

  const loadSales = async () => {
    let data: Sale[];
    
    switch (filter) {
      case 'unpaid':
        data = await creditSalesAPI.getUnpaidCreditSales();
        break;
      case 'partial':
        data = await creditSalesAPI.getPartiallyPaidSales();
        break;
      case 'overdue':
        data = await creditSalesAPI.getOverdueSales(30);
        break;
      default:
        const response = await fetch('/api/sales/?payment_type=CREDIT&has_outstanding_balance=true');
        const json = await response.json();
        data = json.results;
    }
    
    setSales(data);
  };

  return (
    <div className="credit-sales-list">
      <div className="filters">
        <button onClick={() => setFilter('all')}>All Outstanding</button>
        <button onClick={() => setFilter('unpaid')}>Unpaid</button>
        <button onClick={() => setFilter('partial')}>Partially Paid</button>
        <button onClick={() => setFilter('overdue')}>Overdue (30+ days)</button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Receipt</th>
            <th>Customer</th>
            <th>Total</th>
            <th>Paid</th>
            <th>Due</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sales.map((sale) => (
            <tr key={sale.id}>
              <td>{sale.receipt_number}</td>
              <td>{sale.customer?.name}</td>
              <td>${sale.total_amount}</td>
              <td>${sale.amount_paid}</td>
              <td>${sale.amount_due}</td>
              <td>
                <span className={`badge badge-${sale.payment_status}`}>
                  {sale.payment_status}
                </span>
              </td>
              <td>
                <div className="progress-bar">
                  <div 
                    className="progress-fill"
                    style={{ width: `${sale.payment_completion_percentage}%` }}
                  />
                </div>
                {sale.payment_completion_percentage}%
              </td>
              <td>
                <button onClick={() => setSelectedSale(sale)}>
                  Record Payment
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedSale && (
        <RecordPaymentDialog
          sale={selectedSale}
          onClose={() => setSelectedSale(null)}
          onSuccess={loadSales}
        />
      )}
    </div>
  );
};
```

### 7.2 Dashboard Widgets

```typescript
// components/CreditSummaryWidget.tsx
export const CreditSummaryWidget: React.FC = () => {
  const [summary, setSummary] = useState<FinancialSummary | null>(null);

  useEffect(() => {
    creditSalesAPI.getSummary().then(setSummary);
  }, []);

  if (!summary) return <div>Loading...</div>;

  return (
    <div className="credit-summary-widget">
      <h3>Credit Sales Overview</h3>
      
      <div className="metrics-grid">
        <div className="metric">
          <div className="metric-label">Total Outstanding</div>
          <div className="metric-value">${summary.total_credit_sales}</div>
          <div className="metric-subtitle">{summary.unpaid_credit_count} sales</div>
        </div>

        <div className="metric">
          <div className="metric-label">Unpaid</div>
          <div className="metric-value text-danger">
            ${summary.credit_health.unpaid_amount}
          </div>
        </div>

        <div className="metric">
          <div className="metric-label">Partially Paid</div>
          <div className="metric-value text-warning">
            ${summary.credit_health.partially_paid_amount}
          </div>
        </div>

        <div className="metric">
          <div className="metric-label">Collection Rate</div>
          <div className="metric-value text-success">
            {summary.credit_health.collection_rate}%
          </div>
        </div>

        <div className="metric">
          <div className="metric-label">Cash on Hand (Profit)</div>
          <div className="metric-value">${summary.cash_on_hand}</div>
          <div className="metric-subtitle">
            Outstanding Profit: ${summary.outstanding_credit}
          </div>
        </div>
      </div>

      <div className="credit-health">
        <h4>Credit Health</h4>
        <div className="health-bar">
          <div 
            className="health-segment unpaid"
            style={{ 
              width: `${summary.credit_health.unpaid_amount / summary.credit_health.total_credit_sales * 100}%` 
            }}
            title={`Unpaid: $${summary.credit_health.unpaid_amount}`}
          />
          <div 
            className="health-segment partial"
            style={{ 
              width: `${summary.credit_health.partially_paid_amount / summary.credit_health.total_credit_sales * 100}%` 
            }}
            title={`Partial: $${summary.credit_health.partially_paid_amount}`}
          />
          <div 
            className="health-segment paid"
            style={{ 
              width: `${summary.credit_health.fully_paid_amount / summary.credit_health.total_credit_sales * 100}%` 
            }}
            title={`Paid: $${summary.credit_health.fully_paid_amount}`}
          />
        </div>
      </div>
    </div>
  );
};
```

---

## 8. Business Rules

### 8.1 Credit Sale Creation

**Requirements:**
- ✅ Customer is REQUIRED for credit sales
- ✅ Customer must have valid contact information
- ✅ Business owner can set credit limits per customer (future enhancement)

**Validation:**
```python
if payment_type == 'CREDIT' and not customer:
    raise ValidationError("Customer is required for credit sales")
```

### 8.2 Payment Recording

**Business Rules:**
1. **Only PENDING or PARTIAL sales** can receive payments
2. **Payment amount** must be > 0
3. **Payment amount** cannot exceed `amount_due`
4. **Multiple payments** allowed until sale is fully paid
5. **Status auto-updates**:
   - PENDING → PARTIAL (first payment < total)
   - PENDING → COMPLETED (first payment = total)
   - PARTIAL → COMPLETED (final payment completes balance)

### 8.3 Customer Balance

**Automatic Updates:**
- When sale completed: `customer.balance += amount_due`
- When payment recorded: `customer.balance -= payment_amount`
- Balance reflects total outstanding across all sales

### 8.4 Audit Trail

**All credit transactions are logged:**
- Sale completion
- Payment recording
- Status changes
- User who performed action
- Timestamp
- IP address

---

## 9. Error Handling

### 9.1 Common Errors

**Cannot Record Payment:**
```json
{
  "error": "Cannot record payment for a COMPLETED sale"
}
```

**Payment Too Large:**
```json
{
  "error": "Payment amount ($250.00) exceeds outstanding balance ($75.00)"
}
```

**Invalid Payment Amount:**
```json
{
  "amount": ["Payment amount must be greater than 0"]
}
```

**Missing Customer:**
```json
{
  "customer": ["Customer is required for credit sales"]
}
```

**Sale Not Found:**
```json
{
  "detail": "Not found."
}
```

### 9.2 Frontend Error Handling

```typescript
try {
  await creditSalesAPI.recordPayment(saleId, paymentData);
  showSuccessMessage('Payment recorded successfully');
} catch (error) {
  if (error.message.includes('exceeds outstanding balance')) {
    showErrorMessage('Payment amount is too large. Check the outstanding balance.');
  } else if (error.message.includes('Cannot record payment')) {
    showErrorMessage('This sale is already fully paid.');
  } else {
    showErrorMessage('Failed to record payment. Please try again.');
  }
}
```

---

## 10. Testing

### 10.1 Test Coverage

**Implemented Tests:**
- `test_credit_payment_tracking.py` - 5 tests, all passing ✅
  - Test 1: Credit sale without payment → PENDING
  - Test 2: Partial payment → PARTIAL status
  - Test 3: Final payment → COMPLETED status
  - Test 4: Serializer fields (payment_status, payment_completion_percentage)
  - Test 5: Payment filters (has_outstanding_balance, payment_status)

**Test Results:**
```
TEST 1: Credit sale without payment → PENDING ✅
TEST 2: Partial payment → PARTIAL status ✅
TEST 3: Final payment → COMPLETED status ✅
TEST 4: New serializer fields working ✅
TEST 5: Payment filters working ✅

VERIFICATION RESULTS:
Sales analyzed: 209
PENDING: 0
PARTIAL: 85 (with partial payments)
COMPLETED: 124 (with full payments)
```

### 10.2 Manual Testing Checklist

**Credit Sale Flow:**
- [ ] Create credit sale with customer
- [ ] Add items to sale
- [ ] Complete sale without payment → Status = PENDING
- [ ] Complete sale with partial payment → Status = PARTIAL
- [ ] Complete sale with full payment → Status = COMPLETED

**Payment Recording:**
- [ ] Record payment on PENDING sale
- [ ] Record multiple payments on same sale
- [ ] Record final payment to complete sale
- [ ] Try to overpay (should fail)
- [ ] Try to pay completed sale (should fail)

**Filtering:**
- [ ] Filter by payment_status=unpaid
- [ ] Filter by payment_status=partial
- [ ] Filter by has_outstanding_balance=true
- [ ] Filter by days_outstanding=30
- [ ] Filter by customer_id

**Summary Metrics:**
- [ ] Verify total_credit_sales matches sum of amount_due
- [ ] Verify unpaid_credit_count matches PENDING + PARTIAL count
- [ ] Verify collection_rate calculation
- [ ] Verify cash_on_hand = total_profit - outstanding_credit

---

## 11. Security Considerations

### 11.1 Permissions

**Required Permissions:**
- Create credit sales: User must have access to storefront
- Record payments: User must be authenticated
- View sales: User must have access to business
- All actions are business-scoped (multi-tenancy)

### 11.2 Audit Logging

**All credit operations are logged:**
```python
AuditLog.log_event(
    event_type='payment.recorded',
    user=request.user,
    sale=sale,
    event_data={
        'amount': str(payment.amount),
        'payment_method': payment.payment_method,
        'previous_status': previous_status,
        'new_status': sale.status
    },
    description=f'Payment of ${payment.amount} recorded',
    ip_address=request.META.get('REMOTE_ADDR'),
    user_agent=request.META.get('HTTP_USER_AGENT')
)
```

---

## 12. Best Practices

### 12.1 Frontend Implementation

**DO:**
- ✅ Validate payment amounts before submission
- ✅ Show clear error messages
- ✅ Refresh sale data after payment
- ✅ Display payment history
- ✅ Use optimistic UI updates with rollback on error
- ✅ Implement loading states
- ✅ Cache summary data with periodic refresh

**DON'T:**
- ❌ Allow negative payment amounts
- ❌ Allow payments exceeding balance
- ❌ Submit payments without user confirmation
- ❌ Store payment data in local state without backend sync

### 12.2 User Experience

**Payment Recording:**
1. Show sale details clearly
2. Pre-fill common payment methods
3. Validate amount in real-time
4. Confirm before submitting
5. Show success message with updated balance
6. Option to print receipt

**Credit Management:**
1. Dashboard widget showing key metrics
2. Quick filters for unpaid/partial/overdue
3. Bulk actions for common tasks
4. Export to Excel/PDF for accounting

---

## 13. Migration from Old System

### 13.1 Data Migration

If migrating from an old system:

```python
# Example migration script
from sales.models import Sale, Payment

# Update existing credit sales
credit_sales = Sale.objects.filter(payment_type='CREDIT')

for sale in credit_sales:
    # Recalculate amounts
    sale.amount_paid = sale.payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    sale.amount_due = sale.total_amount - sale.amount_paid
    
    # Update status
    if sale.amount_due == Decimal('0'):
        sale.status = 'COMPLETED'
    elif sale.amount_paid > Decimal('0'):
        sale.status = 'PARTIAL'
    else:
        sale.status = 'PENDING'
    
    sale.save()
```

### 13.2 Backward Compatibility

**Old fields still available:**
- `total_amount` - unchanged
- `status` - enhanced with PARTIAL state
- Existing endpoints still work

**New features are additive:**
- `payment_status` - new computed field
- `payment_completion_percentage` - new computed field
- `record_payment` endpoint - new
- Enhanced filters - new

---

## 14. Support and Resources

### 14.1 Additional Documentation

- [API Documentation](./COMPREHENSIVE_API_DOCUMENTATION.md)
- [Cash on Hand Implementation](./CASH_ON_HAND_PROFIT_IMPLEMENTATION.md)
- [Credit Payment Tracking Tests](./CREDIT_SALES_PAYMENT_TRACKING.md)
- [Financial Summaries](./FINANCIAL_SUMMARIES_IMPLEMENTATION_SUMMARY.md)

### 14.2 Example Code Repository

See `test_credit_payment_tracking.py` for complete working examples of:
- Creating credit sales
- Recording payments
- Filtering sales
- Testing payment scenarios

---

## Appendix A: Complete API Reference

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sales/` | List sales (with filters) |
| POST | `/api/sales/` | Create new sale |
| GET | `/api/sales/{id}/` | Get sale details |
| POST | `/api/sales/{id}/add_item/` | Add item to sale |
| POST | `/api/sales/{id}/complete_sale/` | Complete sale |
| POST | `/api/sales/{id}/record_payment/` | Record payment |
| GET | `/api/sales/{id}/payments/` | Get payment history |
| GET | `/api/sales/summary/` | Get financial summary |

### Filter Parameters Reference

```
?status=PENDING,PARTIAL,COMPLETED
?payment_type=CASH,CARD,CREDIT,MOBILE
?payment_status=unpaid,partial,paid
?has_outstanding_balance=true,false
?days_outstanding=30
?min_amount_due=100.00
?max_amount_due=1000.00
?customer_id=uuid
?date_from=2025-01-01
?date_to=2025-01-31
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-07  
**Author:** GitHub Copilot  
**Status:** ✅ Production Ready
