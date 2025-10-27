"""
CSV exporters for all report types.

These exporters convert report data into CSV format for easier importing into 
spreadsheet applications and other data processing tools.
"""

import csv
from io import StringIO
from typing import Any, Dict, List
from decimal import Decimal


class BaseCSVExporter:
    """Base class for CSV exporters"""
    
    content_type = 'text/csv'
    file_extension = 'csv'
    
    @staticmethod
    def _format_value(value: Any) -> str:
        """Format a value for CSV output"""
        if value is None:
            return ''
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        return str(value)
    
    @staticmethod
    def _write_section_header(writer: csv.writer, title: str) -> None:
        """Write a section header in the CSV"""
        writer.writerow([])
        writer.writerow([title])
        writer.writerow([])


class SalesCSVExporter(BaseCSVExporter):
    """CSV exporter for sales data - exports all sales and line items"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export sales data to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Sales Export Report'])
        writer.writerow(['Generated At', data.get('generated_at', '')])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['Summary Metrics'])
        writer.writerow(['Metric', 'Value'])
        
        summary_metrics = [
            ('Total Sales Count', 'total_sales'),
            ('Total Revenue', 'total_revenue'),
            ('Net Sales (excl. tax & discounts)', 'net_sales'),
            ('Total Tax Collected', 'total_tax'),
            ('Total Discounts Given', 'total_discounts'),
            ('Total Cost of Goods Sold', 'total_cogs'),
            ('Total Gross Profit', 'total_profit'),
            ('Profit Margin %', 'profit_margin_percent'),
            ('Total Amount Paid', 'amount_paid'),
            ('Total Amount Refunded', 'amount_refunded'),
            ('Outstanding Balance', 'outstanding_balance'),
        ]
        
        for label, key in summary_metrics:
            value = data['summary'].get(key, '')
            writer.writerow([label, self._format_value(value)])
        
        # Sales detail section
        self._write_section_header(writer, 'Sales Details')
        
        sales_headers = [
            'Receipt Number', 'Date', 'Time', 'Storefront', 'Cashier',
            'Customer Name', 'Customer Type', 'Sale Type', 'Status',
            'Subtotal', 'Discount', 'Tax', 'Total', 
            'Amount Paid', 'Amount Refunded', 'Amount Due',
            'Payment Type', 'Notes'
        ]
        writer.writerow(sales_headers)
        
        for sale in data.get('sales', []):
            writer.writerow([
                self._format_value(sale.get('receipt_number', '')),
                self._format_value(sale.get('date', '')),
                self._format_value(sale.get('time', '')),
                self._format_value(sale.get('storefront', '')),
                self._format_value(sale.get('cashier', '')),
                self._format_value(sale.get('customer_name', '')),
                self._format_value(sale.get('customer_type', '')),
                self._format_value(sale.get('sale_type', '')),
                self._format_value(sale.get('status', '')),
                self._format_value(sale.get('subtotal', '')),
                self._format_value(sale.get('discount', '')),
                self._format_value(sale.get('tax', '')),
                self._format_value(sale.get('total', '')),
                self._format_value(sale.get('amount_paid', '')),
                self._format_value(sale.get('amount_refunded', '')),
                self._format_value(sale.get('amount_due', '')),
                self._format_value(sale.get('payment_type', '')),
                self._format_value(sale.get('notes', '')),
            ])
        
        # Line items section
        self._write_section_header(writer, 'Line Items')
        
        item_headers = [
            'Receipt Number', 'Product Name', 'SKU', 'Category',
            'Quantity', 'Unit Price', 'Total Price', 'COGS', 'Profit', 'Margin %'
        ]
        writer.writerow(item_headers)
        
        for sale in data.get('sales', []):
            for item in sale.get('items', []):
                writer.writerow([
                    self._format_value(sale.get('receipt_number', '')),
                    self._format_value(item.get('product_name', '')),
                    self._format_value(item.get('sku', '')),
                    self._format_value(item.get('category', '')),
                    self._format_value(item.get('quantity', '')),
                    self._format_value(item.get('unit_price', '')),
                    self._format_value(item.get('total_price', '')),
                    self._format_value(item.get('cogs', '')),
                    self._format_value(item.get('profit', '')),
                    self._format_value(item.get('margin_percent', '')),
                ])
        
        # Return as bytes
        return output.getvalue().encode('utf-8')


class CustomerCSVExporter(BaseCSVExporter):
    """CSV exporter for customer data with credit aging"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export customer data to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Customer Export Report'])
        writer.writerow(['Generated At', data.get('generated_at', '')])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['Customer Statistics'])
        writer.writerow(['Metric', 'Value'])
        
        summary_metrics = [
            ('Total Customers', 'total_customers'),
            ('Retail Customers', 'retail_customers'),
            ('Wholesale Customers', 'wholesale_customers'),
            ('Active Customers', 'active_customers'),
            ('Blocked Customers', 'blocked_customers'),
            ('Total Credit Limit', 'total_credit_limit'),
            ('Total Outstanding Balance', 'total_outstanding_balance'),
            ('Total Available Credit', 'total_available_credit'),
        ]
        
        for label, key in summary_metrics:
            value = data['summary'].get(key, '')
            writer.writerow([label, self._format_value(value)])
        
        writer.writerow([])
        writer.writerow(['Aging Analysis Summary'])
        writer.writerow(['Category', 'Amount'])
        
        aging_metrics = [
            ('Current (0-30 days)', 'aging_current'),
            ('31-60 days', 'aging_31_60'),
            ('61-90 days', 'aging_61_90'),
            ('Over 90 days', 'aging_over_90'),
            ('Total Overdue', 'total_overdue'),
        ]
        
        for label, key in aging_metrics:
            value = data['summary'].get(key, '')
            writer.writerow([label, self._format_value(value)])
        
        # Customer detail section
        self._write_section_header(writer, 'Customer Details')
        
        customer_headers = [
            'Customer ID', 'Name', 'Email', 'Phone', 'Address',
            'Customer Type', 'Contact Person',
            'Credit Limit', 'Outstanding Balance', 'Available Credit',
            'Credit Terms (days)', 'Credit Blocked',
            'Total Sales Count', 'Total Sales Amount', 'Average Sale',
            'Last Sale Date', 'First Sale Date',
            'Active', 'Created Date', 'Created By'
        ]
        writer.writerow(customer_headers)
        
        for customer in data.get('customers', []):
            writer.writerow([
                self._format_value(customer.get('customer_id', '')),
                self._format_value(customer.get('name', '')),
                self._format_value(customer.get('email', '')),
                self._format_value(customer.get('phone', '')),
                self._format_value(customer.get('address', '')),
                self._format_value(customer.get('customer_type', '')),
                self._format_value(customer.get('contact_person', '')),
                self._format_value(customer.get('credit_limit', '')),
                self._format_value(customer.get('outstanding_balance', '')),
                self._format_value(customer.get('available_credit', '')),
                self._format_value(customer.get('credit_terms_days', '')),
                self._format_value(customer.get('credit_blocked', '')),
                self._format_value(customer.get('total_sales_count', '')),
                self._format_value(customer.get('total_sales_amount', '')),
                self._format_value(customer.get('average_sale_amount', '')),
                self._format_value(customer.get('last_sale_date', '')),
                self._format_value(customer.get('first_sale_date', '')),
                self._format_value(customer.get('is_active', '')),
                self._format_value(customer.get('created_at', '')),
                self._format_value(customer.get('created_by', '')),
            ])
        
        # Credit aging section
        self._write_section_header(writer, 'Credit Aging Analysis')
        
        aging_headers = [
            'Customer Name', 'Customer Type', 'Credit Limit', 'Outstanding Balance',
            'Current (0-30)', '31-60 Days', '61-90 Days', 'Over 90 Days',
            'Total Overdue', 'Oldest Invoice (days)', 'Credit Blocked'
        ]
        writer.writerow(aging_headers)
        
        for customer in data.get('customers', []):
            writer.writerow([
                self._format_value(customer.get('name', '')),
                self._format_value(customer.get('customer_type', '')),
                self._format_value(customer.get('credit_limit', '')),
                self._format_value(customer.get('outstanding_balance', '')),
                self._format_value(customer.get('aging_current', '')),
                self._format_value(customer.get('aging_31_60', '')),
                self._format_value(customer.get('aging_61_90', '')),
                self._format_value(customer.get('aging_over_90', '')),
                self._format_value(customer.get('total_overdue', '')),
                self._format_value(customer.get('oldest_invoice_days', '')),
                self._format_value(customer.get('credit_blocked', '')),
            ])
        
        # Credit transactions section (if available)
        if data.get('credit_transactions'):
            self._write_section_header(writer, 'Credit Transactions')
            
            txn_headers = [
                'Customer Name', 'Date', 'Transaction Type',
                'Amount', 'Balance Before', 'Balance After', 'Reference'
            ]
            writer.writerow(txn_headers)
            
            for txn in data['credit_transactions']:
                writer.writerow([
                    self._format_value(txn.get('customer_name', '')),
                    self._format_value(txn.get('date', '')),
                    self._format_value(txn.get('transaction_type', '')),
                    self._format_value(txn.get('amount', '')),
                    self._format_value(txn.get('balance_before', '')),
                    self._format_value(txn.get('balance_after', '')),
                    self._format_value(txn.get('reference', '')),
                ])
        
        # Return as bytes
        return output.getvalue().encode('utf-8')


class InventoryCSVExporter(BaseCSVExporter):
    """CSV exporter for inventory data"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export inventory data to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Inventory Export Report'])
        writer.writerow(['Export Date', data['summary'].get('export_date', '')])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['Inventory Statistics'])
        writer.writerow(['Metric', 'Value'])
        
        summary_metrics = [
            ('Total Unique Products', 'total_unique_products'),
            ('Total Quantity in Stock', 'total_quantity_in_stock'),
            ('Total Inventory Value', 'total_inventory_value'),
            ('Out of Stock Items', 'out_of_stock_items'),
            ('Low Stock Items', 'low_stock_items'),
            ('In Stock Items', 'in_stock_items'),
            ('Number of Storefronts', 'storefronts_count'),
        ]
        
        for label, key in summary_metrics:
            value = data['summary'].get(key, 0)
            writer.writerow([label, self._format_value(value)])
        
        # Storefront breakdown
        writer.writerow([])
        writer.writerow(['Storefront Breakdown'])
        writer.writerow(['Storefront', 'Items', 'Quantity', 'Value'])
        
        idx = 1
        while f'storefront_{idx}_name' in data['summary']:
            writer.writerow([
                self._format_value(data['summary'][f'storefront_{idx}_name']),
                self._format_value(data['summary'][f'storefront_{idx}_items']),
                self._format_value(data['summary'][f'storefront_{idx}_quantity']),
                self._format_value(data['summary'][f'storefront_{idx}_value']),
            ])
            idx += 1
        
        # Stock items section
        self._write_section_header(writer, 'Stock Items')
        
        item_headers = [
            'Product ID', 'Product Name', 'SKU', 'Barcode', 'Storefront',
            'Quantity in Stock', 'Reorder Level', 'Unit of Measure', 'Stock Status',
            'Unit Cost', 'Selling Price', 'Total Value', 'Profit Margin', 'Margin %',
            'Last Updated', 'Created At', 'Created By'
        ]
        writer.writerow(item_headers)
        
        for item in data.get('stock_items', []):
            writer.writerow([
                self._format_value(item.get('product_id', '')),
                self._format_value(item.get('product_name', '')),
                self._format_value(item.get('sku', '')),
                self._format_value(item.get('barcode', '')),
                self._format_value(item.get('storefront', '')),
                self._format_value(item.get('quantity_in_stock', 0)),
                self._format_value(item.get('reorder_level', 0)),
                self._format_value(item.get('unit_of_measure', '')),
                self._format_value(item.get('stock_status', '')),
                self._format_value(item.get('unit_cost', '')),
                self._format_value(item.get('selling_price', '')),
                self._format_value(item.get('total_value', '')),
                self._format_value(item.get('profit_margin', '')),
                self._format_value(item.get('margin_percentage', '')),
                self._format_value(item.get('last_updated', '')),
                self._format_value(item.get('created_at', '')),
                self._format_value(item.get('created_by', '')),
            ])
        
        # Stock movements section (if available)
        if data.get('stock_movements'):
            self._write_section_header(writer, 'Stock Movements')
            
            movement_headers = [
                'Date', 'Product Name', 'SKU', 'Storefront', 'Adjustment Type',
                'Quantity Before', 'Quantity Adjusted', 'Quantity After', 'Reason', 'Performed By'
            ]
            writer.writerow(movement_headers)
            
            for movement in data['stock_movements']:
                writer.writerow([
                    self._format_value(movement.get('date', '')),
                    self._format_value(movement.get('product_name', '')),
                    self._format_value(movement.get('sku', '')),
                    self._format_value(movement.get('storefront', '')),
                    self._format_value(movement.get('adjustment_type', '')),
                    self._format_value(movement.get('quantity_before', '')),
                    self._format_value(movement.get('quantity_adjusted', '')),
                    self._format_value(movement.get('quantity_after', '')),
                    self._format_value(movement.get('reason', '')),
                    self._format_value(movement.get('performed_by', '')),
                ])
        
        # Return as bytes
        return output.getvalue().encode('utf-8')


class AuditLogCSVExporter(BaseCSVExporter):
    """CSV exporter for audit log data"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export audit logs to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Audit Log Export Report'])
        writer.writerow(['Export Date', data['summary'].get('export_date', '')])
        writer.writerow(['Date Range', f"{data['summary'].get('date_range_start', '')} to {data['summary'].get('date_range_end', '')}"])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['Audit Statistics'])
        writer.writerow(['Metric', 'Value'])
        
        summary_metrics = [
            ('Total Events', 'total_events'),
            ('First Event', 'first_event_time'),
            ('Last Event', 'last_event_time'),
            ('Unique Users', 'unique_users'),
            ('Unique Event Types', 'unique_event_types'),
        ]
        
        for label, key in summary_metrics:
            value = data['summary'].get(key, 0)
            writer.writerow([label, self._format_value(value)])
        
        # Event type breakdown
        writer.writerow([])
        writer.writerow(['Top Event Types'])
        writer.writerow(['Event Type', 'Count'])
        
        idx = 1
        while f'event_{idx}_type' in data['summary']:
            writer.writerow([
                self._format_value(data['summary'][f'event_{idx}_type']),
                self._format_value(data['summary'][f'event_{idx}_count']),
            ])
            idx += 1
        
        # User activity breakdown
        writer.writerow([])
        writer.writerow(['Top Users'])
        writer.writerow(['User', 'Activity Count'])
        
        idx = 1
        while f'user_{idx}_name' in data['summary']:
            writer.writerow([
                self._format_value(data['summary'][f'user_{idx}_name']),
                self._format_value(data['summary'][f'user_{idx}_count']),
            ])
            idx += 1
        
        # Audit logs section
        self._write_section_header(writer, 'Audit Logs')
        
        log_headers = [
            'Log ID', 'Timestamp', 'Event Type', 'Event Label', 'User Email', 'User Name',
            'Entity Type', 'Entity ID', 'Entity Name', 'Description', 'Event Details',
            'IP Address', 'User Agent'
        ]
        writer.writerow(log_headers)
        
        for log in data.get('audit_logs', []):
            writer.writerow([
                self._format_value(log.get('log_id', '')),
                self._format_value(log.get('timestamp', '')),
                self._format_value(log.get('event_type', '')),
                self._format_value(log.get('event_label', '')),
                self._format_value(log.get('user_email', '')),
                self._format_value(log.get('user_name', '')),
                self._format_value(log.get('entity_type', '')),
                self._format_value(log.get('entity_id', '')),
                self._format_value(log.get('entity_name', '')),
                self._format_value(log.get('description', '')),
                self._format_value(log.get('event_details', '')),
                self._format_value(log.get('ip_address', '')),
                self._format_value(log.get('user_agent', '')),
            ])
        
        # Return as bytes
        return output.getvalue().encode('utf-8')
