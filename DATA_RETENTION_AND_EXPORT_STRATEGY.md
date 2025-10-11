# Data Retention and Export Strategy for SaaS POS Platform

**Document Version:** 1.0  
**Date:** October 11, 2025  
**Purpose:** Define critical business data metrics and export functionality requirements for 3-month data retention policy

---

## Executive Summary

As a SaaS POS platform serving primarily small businesses, we implement a **3-month data retention policy** for operational data. This document outlines:

1. **Critical business metrics** that must be preserved
2. **Export functionality requirements** (primarily Excel/CSV format)
3. **Implementation priorities** and timelines
4. **Regulatory and legal considerations**

### Key Principles

- **Business Continuity**: Customers must have access to all business-critical data
- **Tax & Compliance**: Ensure exportable data meets accounting and tax audit requirements
- **Simple Formats**: Excel/CSV for universal accessibility
- **Automated Options**: Monthly/quarterly automated exports
- **Retention Buffer**: Recommend 90-day retention with 30-day warning period

---

## 1. Critical Business Metrics & Data Categories

### 1.1 Financial & Tax Data (HIGHEST PRIORITY)

#### Sales & Revenue Data
**Retention Requirement:** Minimum 7 years (tax purposes)  
**Export Format:** Excel with multiple sheets

**Core Data Fields:**
- Sale ID, Receipt Number, Transaction Date & Time
- Customer Name, Type (Retail/Wholesale), Contact Details
- Storefront Name & Location
- Staff/Cashier Name
- **Line Items:**
  - Product Name, SKU, Category
  - Quantity, Unit Price, Total Price
  - Discount Amount, Tax Amount
  - Cost of Goods Sold (COGS)
  - Profit per Item
- **Sale Totals:**
  - Subtotal (before discount/tax)
  - Total Discount
  - Total Tax
  - Final Amount
  - Amount Paid, Payment Method(s)
  - Outstanding Balance (for credit sales)
- Payment Type (Cash/Card/Mobile/Credit/Mixed)
- Sale Status (Draft/Pending/Completed/Partial/Refunded/Cancelled)
- Refund Information (if applicable)
- Manager Override details (if any)

**Related Models:**
- `sales.Sale`
- `sales.SaleItem`
- `sales.Payment`
- `sales.Refund`
- `sales.RefundItem`

#### Tax Reports
**Export Fields:**
- Period (Daily/Weekly/Monthly/Quarterly/Annual)
- Total Sales (Gross Revenue)
- Tax Collected by Rate
- Exempt Sales
- Refunds & Discounts
- Net Sales

#### Profit & Loss (P&L) Summary
**Export Fields:**
- Period Range
- Total Revenue (by sale type: retail/wholesale)
- Total COGS
- Gross Profit & Margin %
- Total Discounts Given
- Total Tax Collected
- Net Sales
- Realized vs Outstanding Revenue

---

### 1.2 Customer Data (HIGH PRIORITY)

**Retention Requirement:** Varies by jurisdiction (typically 5-7 years for business customers)  
**Export Format:** Excel

**Core Data Fields:**
- Customer ID, Name, Type (Retail/Wholesale)
- Contact Information (Email, Phone, Address)
- Contact Person (for businesses)
- **Credit Management:**
  - Credit Limit
  - Outstanding Balance
  - Credit Terms (days)
  - Credit Status (Active/Blocked)
  - Overdue Amount
- **Transaction History:**
  - Total Sales Amount
  - Number of Transactions
  - Average Transaction Value
  - Last Purchase Date
  - Payment History
- Active Status
- Creation Date, Last Updated

**Related Models:**
- `sales.Customer`
- `sales.CreditTransaction`

---

### 1.3 Inventory Data (HIGH PRIORITY)

#### Current Inventory Snapshot
**Export Format:** Excel with valuation

**Core Data Fields:**
- Product ID, Name, SKU, Barcode
- Category
- Unit of Measure
- **Stock Levels:**
  - Current Quantity (by location: warehouse/storefront)
  - Reserved Quantity
  - Available Quantity
  - Reorder Level, Maximum Level
- **Valuation:**
  - Unit Cost (Latest/Average)
  - Total Inventory Value
  - Retail Price, Wholesale Price
  - Expected Profit per Unit
  - Margin %
- Supplier Information
- Product Status (Active/Inactive)

#### Stock Movement History
**Core Data Fields:**
- Date & Time
- Product Details
- Movement Type (Purchase/Sale/Adjustment/Transfer)
- Quantity In/Out
- Location (Warehouse/Storefront)
- Reference Number (Stock Receipt/Sale/Adjustment ID)
- Performed By (User)
- Reason (for adjustments)

#### Stock Adjustments
**Core Data Fields:**
- Adjustment ID, Date
- Product Details
- Quantity Adjusted
- Adjustment Type (Damage/Spoilage/Theft/Count Correction)
- Reason & Notes
- Financial Impact
- Approved By, Status

**Related Models:**
- `inventory.Product`
- `inventory.Stock`
- `inventory.StockProduct`
- `inventory.StoreFrontInventory`
- `inventory.stock_adjustments.StockAdjustment`

---

### 1.4 Supplier & Purchasing Data (MEDIUM-HIGH PRIORITY)

**Export Format:** Excel

**Core Data Fields:**
- Supplier ID, Name, Contact Information
- **Purchase History:**
  - Stock Receipt ID, Date
  - Products Purchased (Name, SKU, Quantity)
  - Unit Cost, Total Cost
  - Batch/Lot Number
  - Expiry Date (if applicable)
  - Warehouse Received
- **Supplier Performance:**
  - Total Purchases (Amount)
  - Number of Orders
  - Average Lead Time
  - Quality Issues (if tracked)
- Payment Terms
- Active Status

**Related Models:**
- `inventory.Supplier`
- `inventory.Stock`
- `inventory.StockProduct`

---

### 1.5 Financial Reconciliation Data (HIGH PRIORITY)

#### Cash Management
**Export Fields:**
- Date
- Storefront
- **Cash Flow:**
  - Opening Cash
  - Cash Sales
  - Cash Payments Received
  - Cash Refunds Given
  - Closing Cash Expected
  - Actual Cash Counted
  - Variance (Over/Short)
- Reconciled By, Date

#### Payment Analysis
**Export Fields:**
- Period
- Payment Method Breakdown (Cash/Card/Mobile/Credit)
- Total Collected per Method
- Outstanding Credit Sales
- Refunds Processed
- Net Cash Flow

**Related Models:**
- `sales.Sale`
- `sales.Payment`
- `sales.CreditTransaction`

---

### 1.6 Credit & Receivables (HIGH PRIORITY)

**Export Format:** Excel with aging report

**Core Data Fields:**
- Customer Name, Type
- Credit Limit vs Outstanding Balance
- **Aging Buckets:**
  - Current (0-30 days)
  - 31-60 days
  - 61-90 days
  - Over 90 days
- Individual Sale Details:
  - Sale Date, Receipt Number
  - Total Amount, Amount Paid, Balance Due
  - Due Date, Days Overdue
- Payment History & Dates
- Credit Status

**Related Models:**
- `sales.Customer`
- `sales.Sale` (where payment_type='CREDIT')
- `sales.CreditTransaction`

---

### 1.7 Staff & User Activity (MEDIUM PRIORITY)

**Export Format:** Excel

**Core Data Fields:**
- User/Staff Name, Role
- **Activity Summary:**
  - Total Sales Processed (Count & Value)
  - Average Transaction Value
  - Refunds Processed
  - Stock Adjustments Made
  - Shift Hours (if tracked)
- Storefront Assignment
- Performance Period
- Manager Overrides Granted

**Related Models:**
- `accounts.User`
- `accounts.BusinessMembership`
- `inventory.StoreFrontEmployee`
- `sales.Sale` (user field)
- `sales.AuditLog`

---

### 1.8 Product Performance Analysis (MEDIUM PRIORITY)

**Export Format:** Excel

**Core Data Fields:**
- Product Name, SKU, Category
- **Sales Performance:**
  - Units Sold
  - Total Revenue
  - Total Profit
  - Average Selling Price
  - Margin %
- **Inventory Metrics:**
  - Current Stock Level
  - Inventory Turnover Rate
  - Days in Stock
  - Stock Value
- Top/Bottom Performers
- Seasonal Trends (if data available)

---

### 1.9 Audit Trail (REGULATORY REQUIREMENT)

**Export Format:** Excel/CSV

**Core Data Fields:**
- Event Timestamp
- Event Type (sale.created, refund.processed, customer.updated, etc.)
- User Performing Action
- Affected Entity (Sale, Customer, Product, etc.)
- Entity ID
- Changes Made (Before/After values)
- IP Address (if tracked)
- Description

**Related Models:**
- `sales.AuditLog`

---

### 1.10 Subscription & Business Account Data (INTERNAL USE)

**For Platform Management** (not necessarily customer-facing export)

**Core Data Fields:**
- Business Name, Owner
- Subscription Plan, Status
- Billing Period, Next Billing Date
- Payment History
- Usage Metrics (Users, Storefronts, Products, Transactions)
- Active Storefronts, Warehouses
- Total Revenue Generated (for platform analytics)

**Related Models:**
- `accounts.Business`
- `subscriptions.Subscription`
- `subscriptions.Invoice`
- `subscriptions.UsageTracking`

---

## 2. Export Functionality Requirements

### 2.1 Export Formats

**Primary Format: Excel (.xlsx)**
- Multiple worksheets for related data (e.g., Sales Summary + Line Items)
- Formatted headers, frozen panes
- Auto-column sizing
- Data validation where applicable

**Secondary Format: CSV**
- Simple, universal compatibility
- One file per data type
- UTF-8 encoding

**Optional Formats:**
- PDF (for printable reports)
- Word (.docx) for documentation

**Current Implementation Status:**
✅ Excel export exists for Inventory Valuation Report (`reports/exporters.py`)
✅ Uses `openpyxl`, `python-docx`, `reportlab`

### 2.2 Required Export Endpoints

#### Sales Exports
```
POST /api/sales/export/
Query Parameters:
- format: excel|csv|pdf
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD
- storefront_id: UUID (optional)
- customer_id: UUID (optional)
- sale_type: RETAIL|WHOLESALE (optional)
- status: COMPLETED|REFUNDED|etc. (optional)
- include_items: true|false (include line items)
```

#### Inventory Exports
```
POST /api/inventory/export/snapshot/
- Current inventory snapshot with valuation
- Stock movement history
- Stock adjustments

POST /api/inventory/export/movements/
- Date range filtering
- Product filtering
- Movement type filtering
```

#### Customer Exports
```
POST /api/customers/export/
- Customer list with credit status
- Transaction history per customer
- Aging report (credit receivables)
```

#### Financial Reports
```
POST /api/reports/financial/export/
- P&L statement
- Cash flow summary
- Tax report
- Payment method analysis
```

#### Supplier & Purchasing
```
POST /api/suppliers/export/
- Supplier directory
- Purchase history
```

#### Audit Trail
```
POST /api/audit/export/
- Complete audit log for date range
- Filterable by event type, user, entity
```

### 2.3 Automated Export Features

**Scheduled Exports** (Future Enhancement)
- Weekly/Monthly/Quarterly automatic generation
- Email delivery to business owner
- Cloud storage integration (Google Drive, Dropbox)

**Pre-Expiry Warnings**
- 30 days before data deletion: Auto-generate comprehensive export
- Email notification with download link
- Reminder at 15 days, 7 days, 1 day

**Bulk Export Option**
- "Export All Data" feature
- Generates ZIP file with all categories
- Recommended before subscription cancellation

---

## 3. Implementation Priority & Timeline

### Phase 1: Critical Exports (Weeks 1-3)
**Priority:** HIGHEST - Tax & Legal Compliance

1. **Sales Export** (with line items, payments, refunds)
2. **Customer Export** (with credit aging)
3. **Inventory Snapshot Export** (with valuation)
4. **Audit Trail Export**

**Success Criteria:**
- Excel format with proper formatting
- Date range filtering
- Business-scoped data (multi-tenant safe)
- Download within 60 seconds for 3 months of data

---

### Phase 2: Financial Reports (Weeks 4-5)
**Priority:** HIGH - Business Intelligence

1. **P&L Report Export**
2. **Tax Summary Export**
3. **Cash Flow & Payment Analysis**
4. **Credit Receivables Aging Report**

---

### Phase 3: Operational Reports (Weeks 6-7)
**Priority:** MEDIUM-HIGH

1. **Stock Movement History Export**
2. **Stock Adjustments Export**
3. **Supplier & Purchase History Export**
4. **Product Performance Analysis**
5. **Staff Activity Report**

---

### Phase 4: Automation & UX (Weeks 8-10)
**Priority:** MEDIUM

1. **Scheduled Exports** (background jobs)
2. **Pre-Expiry Warnings** (30/15/7/1 day notifications)
3. **Bulk "Export All Data" Feature**
4. **Export History** (track what was exported and when)
5. **Export Templates** (save common export configurations)

---

## 4. Technical Implementation Guide

### 4.1 Base Export Service Class

```python
# reports/services/base_exporter.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from django.db.models import QuerySet
from django.contrib.auth import get_user_model

User = get_user_model()

class BaseDataExporter(ABC):
    """Base class for all data exporters"""
    
    def __init__(self, user: User):
        self.user = user
        self.business_ids = self._get_business_ids()
    
    def _get_business_ids(self) -> List:
        """Get businesses accessible to user"""
        from accounts.models import BusinessMembership
        
        if self.user.is_superuser:
            return None  # Access all
        
        memberships = BusinessMembership.objects.filter(
            user=self.user,
            is_active=True
        ).values_list('business_id', flat=True)
        
        return list(memberships)
    
    @abstractmethod
    def build_queryset(self, filters: Dict[str, Any]) -> QuerySet:
        """Build filtered queryset - implement in subclass"""
        pass
    
    @abstractmethod
    def serialize_data(self, queryset: QuerySet) -> Dict[str, Any]:
        """Convert queryset to export format - implement in subclass"""
        pass
    
    def export(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Main export method"""
        queryset = self.build_queryset(filters)
        data = self.serialize_data(queryset)
        return data
```

### 4.2 Sales Export Service

```python
# reports/services/sales.py

from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from sales.models import Sale, SaleItem, Payment, Refund
from .base_exporter import BaseDataExporter

class SalesExporter(BaseDataExporter):
    """Export sales data with line items"""
    
    def build_queryset(self, filters: Dict[str, Any]):
        queryset = Sale.objects.select_related(
            'business', 'storefront', 'customer', 'user'
        ).prefetch_related(
            'sale_items__product',
            'payments',
            'refunds'
        )
        
        # Filter by business
        if self.business_ids:
            queryset = queryset.filter(business_id__in=self.business_ids)
        
        # Date range
        if filters.get('start_date'):
            queryset = queryset.filter(created_at__gte=filters['start_date'])
        if filters.get('end_date'):
            queryset = queryset.filter(created_at__lte=filters['end_date'])
        
        # Storefront filter
        if filters.get('storefront_id'):
            queryset = queryset.filter(storefront_id=filters['storefront_id'])
        
        # Customer filter
        if filters.get('customer_id'):
            queryset = queryset.filter(customer_id=filters['customer_id'])
        
        # Sale type
        if filters.get('sale_type'):
            queryset = queryset.filter(type=filters['sale_type'])
        
        # Status
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        else:
            # Exclude DRAFT by default
            queryset = queryset.exclude(status='DRAFT')
        
        return queryset.order_by('-created_at')
    
    def serialize_data(self, queryset):
        """Convert to export-ready format"""
        
        # Summary sheet data
        summary = {
            'total_sales': queryset.count(),
            'total_revenue': queryset.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00'),
            'total_tax': queryset.aggregate(
                total=Sum('tax_amount')
            )['total'] or Decimal('0.00'),
            'total_discounts': queryset.aggregate(
                total=Sum('discount_amount')
            )['total'] or Decimal('0.00'),
            'amount_paid': queryset.aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0.00'),
            'amount_refunded': queryset.aggregate(
                total=Sum('amount_refunded')
            )['total'] or Decimal('0.00'),
            'outstanding_balance': queryset.aggregate(
                total=Sum('amount_due')
            )['total'] or Decimal('0.00'),
        }
        
        # Calculate COGS and profit from line items
        all_items = SaleItem.objects.filter(
            sale__in=queryset
        ).aggregate(
            total_cogs=Sum('cost_of_goods_sold'),
            total_profit=Sum('profit')
        )
        
        summary['total_cogs'] = all_items['total_cogs'] or Decimal('0.00')
        summary['total_profit'] = all_items['total_profit'] or Decimal('0.00')
        
        if summary['total_revenue'] > 0:
            summary['profit_margin_percent'] = (
                (summary['total_profit'] / summary['total_revenue']) * 100
            ).quantize(Decimal('0.01'))
        else:
            summary['profit_margin_percent'] = Decimal('0.00')
        
        # Detail rows (sales with line items)
        sales_data = []
        for sale in queryset:
            sale_row = {
                'receipt_number': sale.receipt_number,
                'date': sale.created_at.strftime('%Y-%m-%d'),
                'time': sale.created_at.strftime('%H:%M:%S'),
                'storefront': sale.storefront.name,
                'cashier': sale.user.get_full_name() if sale.user else '',
                'customer_name': sale.customer.name if sale.customer else 'Walk-in',
                'customer_type': sale.customer.customer_type if sale.customer else 'RETAIL',
                'sale_type': sale.type,
                'status': sale.status,
                'subtotal': str(sale.subtotal),
                'discount': str(sale.discount_amount),
                'tax': str(sale.tax_amount),
                'total': str(sale.total_amount),
                'amount_paid': str(sale.amount_paid),
                'amount_refunded': str(sale.amount_refunded),
                'amount_due': str(sale.amount_due),
                'payment_type': sale.payment_type,
                'notes': sale.notes or '',
            }
            
            # Line items for this sale
            items = []
            for item in sale.sale_items.all():
                items.append({
                    'product_name': item.product.name,
                    'sku': item.product.sku,
                    'category': item.product.category.name if item.product.category else '',
                    'quantity': str(item.quantity),
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price),
                    'cogs': str(item.cost_of_goods_sold),
                    'profit': str(item.profit),
                })
            
            sale_row['items'] = items
            sales_data.append(sale_row)
        
        return {
            'summary': summary,
            'sales': sales_data,
            'generated_at': timezone.now(),
        }
```

### 4.3 Excel Export Format Builder

```python
# reports/exporters.py (extend existing)

class SalesExcelExporter(BaseReportExporter):
    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    file_extension = 'xlsx'
    
    def export(self, report_data: Dict[str, Any]) -> bytes:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter
        
        workbook = Workbook()
        
        # Summary Sheet
        summary_sheet = workbook.active
        summary_sheet.title = 'Summary'
        
        # Header
        summary_sheet['A1'] = 'Sales Export Report'
        summary_sheet['A1'].font = Font(size=16, bold=True)
        summary_sheet.merge_cells('A1:B1')
        
        summary_sheet['A2'] = 'Generated At'
        summary_sheet['B2'] = report_data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        row = 4
        summary_sheet[f'A{row}'] = 'Summary Metrics'
        summary_sheet[f'A{row}'].font = Font(bold=True, size=12)
        row += 1
        
        for key, value in report_data['summary'].items():
            summary_sheet[f'A{row}'] = key.replace('_', ' ').title()
            summary_sheet[f'B{row}'] = str(value)
            row += 1
        
        # Sales Detail Sheet
        detail_sheet = workbook.create_sheet(title='Sales Detail')
        
        # Headers
        headers = [
            'Receipt Number', 'Date', 'Time', 'Storefront', 'Cashier',
            'Customer Name', 'Customer Type', 'Sale Type', 'Status',
            'Subtotal', 'Discount', 'Tax', 'Total', 
            'Amount Paid', 'Amount Refunded', 'Amount Due',
            'Payment Type', 'Notes'
        ]
        
        for col_num, header in enumerate(headers, 1):
            cell = detail_sheet.cell(row=1, column=col_num)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
        
        row = 2
        for sale in report_data['sales']:
            for col_num, header in enumerate(headers, 1):
                field_name = header.lower().replace(' ', '_')
                value = sale.get(field_name, '')
                detail_sheet.cell(row=row, column=col_num, value=value)
            row += 1
        
        # Line Items Sheet
        items_sheet = workbook.create_sheet(title='Line Items')
        
        item_headers = [
            'Receipt Number', 'Product Name', 'SKU', 'Category',
            'Quantity', 'Unit Price', 'Total Price', 'COGS', 'Profit'
        ]
        
        for col_num, header in enumerate(item_headers, 1):
            cell = items_sheet.cell(row=1, column=col_num)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
        
        row = 2
        for sale in report_data['sales']:
            for item in sale.get('items', []):
                items_sheet.cell(row=row, column=1, value=sale['receipt_number'])
                items_sheet.cell(row=row, column=2, value=item['product_name'])
                items_sheet.cell(row=row, column=3, value=item['sku'])
                items_sheet.cell(row=row, column=4, value=item['category'])
                items_sheet.cell(row=row, column=5, value=item['quantity'])
                items_sheet.cell(row=row, column=6, value=item['unit_price'])
                items_sheet.cell(row=row, column=7, value=item['total_price'])
                items_sheet.cell(row=row, column=8, value=item['cogs'])
                items_sheet.cell(row=row, column=9, value=item['profit'])
                row += 1
        
        # Auto-size columns
        for sheet in [summary_sheet, detail_sheet, items_sheet]:
            for column_cells in sheet.columns:
                max_length = 0
                column = get_column_letter(column_cells[0].column)
                for cell in column_cells:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                sheet.column_dimensions[column].width = adjusted_width
        
        # Save to bytes
        from io import BytesIO
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
```

### 4.4 View for Sales Export

```python
# reports/views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status

from .services.sales import SalesExporter
from .exporters import SalesExcelExporter
from .serializers import SalesExportRequestSerializer

class SalesExportView(APIView):
    """Export sales data to Excel/CSV"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = SalesExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        filters = serializer.validated_data
        export_format = filters.pop('format', 'excel')
        
        # Build data
        exporter = SalesExporter(user=request.user)
        data = exporter.export(filters)
        
        # Generate file
        if export_format == 'excel':
            file_exporter = SalesExcelExporter()
            file_bytes = file_exporter.export(data)
            content_type = file_exporter.content_type
            extension = file_exporter.file_extension
        # Add CSV, PDF exporters as needed
        
        # Generate filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"sales_export_{timestamp}.{extension}"
        
        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
```

### 4.5 Request Serializer

```python
# reports/serializers.py

from rest_framework import serializers

class SalesExportRequestSerializer(serializers.Serializer):
    format = serializers.ChoiceField(
        choices=['excel', 'csv', 'pdf'],
        default='excel'
    )
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    storefront_id = serializers.UUIDField(required=False)
    customer_id = serializers.UUIDField(required=False)
    sale_type = serializers.ChoiceField(
        choices=['RETAIL', 'WHOLESALE'],
        required=False
    )
    status = serializers.ChoiceField(
        choices=['DRAFT', 'PENDING', 'COMPLETED', 'PARTIAL', 'REFUNDED', 'CANCELLED'],
        required=False
    )
    include_items = serializers.BooleanField(default=True)
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("start_date must be before end_date")
        return data
```

---

## 5. Legal & Regulatory Considerations

### 5.1 Data Retention Laws (by Jurisdiction)

**Tax Records:**
- **Ghana:** 5 years from end of fiscal year
- **Nigeria:** 6 years
- **Kenya:** 5 years
- **US (IRS):** 7 years
- **EU (VAT):** Varies by country (5-10 years)

**Recommendation:** **7-year retention for financial data**

### 5.2 GDPR & Privacy Compliance

**Right to Data Portability (GDPR Article 20):**
- Customers must be able to export their data in machine-readable format
- Excel/CSV fulfills this requirement

**Right to Erasure:**
- Conflicts with tax retention requirements
- Solution: Anonymize personal data after business relationship ends, but retain transaction records

### 5.3 Terms of Service Recommendations

**Proposed Clause:**
> "While active data is retained for 90 days on our platform, we strongly recommend monthly data exports for your records. You are responsible for maintaining your own backups. Financial and tax data should be retained for a minimum of 7 years per applicable tax laws. We will notify you 30 days before any scheduled data deletion."

---

## 6. User Communication Plan

### 6.1 Onboarding
- Explain 3-month active data retention
- Recommend monthly export schedule
- Provide export tutorial/video

### 6.2 Regular Reminders
- Monthly email: "Export Your Data for [Month]"
- Include direct export links

### 6.3 Pre-Deletion Warnings
- **30 days before:** Email with "Export All Data" button
- **15 days before:** Second reminder
- **7 days before:** Urgent notice
- **1 day before:** Final warning

### 6.4 Post-Deletion
- Confirmation email: "Data archived. Download link (available 7 days)"

---

## 7. Future Enhancements

### 7.1 Cloud Storage Integration
- Auto-export to Google Drive, Dropbox, OneDrive
- Business owner authorizes access
- Seamless monthly backups

### 7.2 Accounting Software Integration
- Export to QuickBooks format
- Export to Xero format
- Direct API sync (premium feature)

### 7.3 Advanced Analytics Dashboards
- Year-over-year comparisons
- Predictive analytics
- Custom report builder

### 7.4 Data Archive Service (Premium)
- Extended retention (1-3 years) for additional fee
- Compliant with "cold storage" pricing model

---

## 8. Testing & Validation Checklist

### Pre-Launch Testing

- [ ] Export generates within 60 seconds for 3 months of data
- [ ] Excel files open correctly in Microsoft Excel 2016+, Google Sheets, LibreOffice
- [ ] CSV files UTF-8 encoded, proper delimiter handling
- [ ] Multi-tenant safety: Users only see their business data
- [ ] Date range filtering works correctly
- [ ] All currency values formatted correctly (2 decimal places)
- [ ] Large datasets (10,000+ sales) export without errors
- [ ] File downloads work on mobile browsers
- [ ] Exported data matches API query results (data integrity check)
- [ ] Audit trail logs all export actions

### User Acceptance Testing

- [ ] Business owners can understand exported data without technical help
- [ ] Accountants can use exported files for tax filing
- [ ] Data can be re-imported to other systems (if needed)

---

## 9. Summary & Action Items

### Immediate Actions (This Week)
1. **Create tickets** for Phase 1 exports (Sales, Customer, Inventory, Audit)
2. **Review legal requirements** for target markets (Ghana, Nigeria, Kenya, etc.)
3. **Update Terms of Service** with data retention policy
4. **Draft email templates** for pre-deletion warnings

### Short-Term (Next 2-4 Weeks)
1. **Implement Phase 1 exports** (Sales, Customer, Inventory, Audit)
2. **Add export buttons** to frontend dashboard
3. **Create export tutorial** documentation/video
4. **Test with pilot users**

### Medium-Term (1-2 Months)
1. **Implement Phase 2-3 exports** (Financial reports, Stock movements, Suppliers)
2. **Build automated export scheduler**
3. **Create pre-deletion warning system**
4. **Add export history tracking**

### Long-Term (3-6 Months)
1. **Cloud storage integration**
2. **Accounting software export formats**
3. **Data archive service** (premium feature)
4. **Advanced analytics** on exported data

---

**Document Prepared By:** AI Assistant  
**Review Required By:** Product Manager, Legal Team, Development Lead  
**Next Review Date:** November 11, 2025
