"""
PDF exporters for all report types.

These exporters convert report data into PDF format for formal reports,
printing, and professional presentations.
"""

from io import BytesIO
from typing import Any, Dict, List
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas


class BasePDFExporter:
    """Base class for PDF exporters"""
    
    content_type = 'application/pdf'
    file_extension = 'pdf'
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        ))
        
        # Metric label style
        self.styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#555555'),
            fontName='Helvetica-Bold'
        ))
        
        # Metric value style
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#000000'),
            alignment=TA_RIGHT
        ))
    
    @staticmethod
    def _format_value(value: Any) -> str:
        """Format a value for PDF output"""
        if value is None:
            return ''
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return str(value)
    
    def _create_header_table(self, title: str, generated_at: str) -> Table:
        """Create a standard header for the PDF"""
        header_data = [
            [Paragraph(title, self.styles['CustomTitle'])],
            [Paragraph(f'Generated: {generated_at}', self.styles['CustomSubtitle'])]
        ]
        
        header_table = Table(header_data, colWidths=[7.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        return header_table
    
    def _create_summary_table(self, metrics: List[tuple], title: str = 'Summary') -> List:
        """Create a summary metrics table"""
        elements = []
        
        elements.append(Paragraph(title, self.styles['SectionHeader']))
        
        # Create table data
        table_data = []
        for label, value in metrics:
            table_data.append([
                Paragraph(label, self.styles['MetricLabel']),
                Paragraph(self._format_value(value), self.styles['MetricValue'])
            ])
        
        # Create table
        summary_table = Table(table_data, colWidths=[4*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 15))
        
        return elements


class SalesPDFExporter(BasePDFExporter):
    """PDF exporter for sales data"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export sales data to PDF format"""
        buffer = BytesIO()
        
        # Use landscape for wider tables
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        story = []
        
        # Header
        generated_at = data.get('generated_at', timezone.now()).strftime('%Y-%m-%d %H:%M:%S')
        story.append(self._create_header_table('Sales Export Report', generated_at))
        story.append(Spacer(1, 20))
        
        # Summary metrics
        summary_metrics = [
            ('Total Sales Count', data['summary'].get('total_sales', 0)),
            ('Total Revenue', f"${data['summary'].get('total_revenue', 0)}"),
            ('Net Sales', f"${data['summary'].get('net_sales', 0)}"),
            ('Total Tax', f"${data['summary'].get('total_tax', 0)}"),
            ('Total Discounts', f"${data['summary'].get('total_discounts', 0)}"),
            ('Total COGS', f"${data['summary'].get('total_cogs', 0)}"),
            ('Total Profit', f"${data['summary'].get('total_profit', 0)}"),
            ('Profit Margin', f"{data['summary'].get('profit_margin_percent', 0)}%"),
        ]
        
        story.extend(self._create_summary_table(summary_metrics, 'Financial Summary'))
        
        # Sales details (limit to 50 for PDF)
        if data.get('sales'):
            story.append(Paragraph('Sales Details (Top 50)', self.styles['SectionHeader']))
            
            headers = ['Receipt', 'Date', 'Customer', 'Type', 'Status', 'Total', 'Paid', 'Due']
            table_data = [headers]
            
            for sale in data['sales'][:50]:
                table_data.append([
                    self._format_value(sale.get('receipt_number', ''))[:15],
                    self._format_value(sale.get('date', '')),
                    self._format_value(sale.get('customer_name', ''))[:20],
                    self._format_value(sale.get('sale_type', '')),
                    self._format_value(sale.get('status', '')),
                    f"${self._format_value(sale.get('total', ''))}",
                    f"${self._format_value(sale.get('amount_paid', ''))}",
                    f"${self._format_value(sale.get('amount_due', ''))}",
                ])
            
            sales_table = Table(table_data, repeatRows=1)
            sales_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            
            story.append(sales_table)
            
            if len(data['sales']) > 50:
                story.append(Spacer(1, 10))
                story.append(Paragraph(
                    f'Showing 50 of {len(data["sales"])} sales. Use Excel or CSV export for complete data.',
                    self.styles['Italic']
                ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.read()


class CustomerPDFExporter(BasePDFExporter):
    """PDF exporter for customer data"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export customer data to PDF format"""
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        story = []
        
        # Header
        generated_at = data.get('generated_at', timezone.now()).strftime('%Y-%m-%d %H:%M:%S')
        story.append(self._create_header_table('Customer Export Report', generated_at))
        story.append(Spacer(1, 20))
        
        # Summary metrics
        summary_metrics = [
            ('Total Customers', data['summary'].get('total_customers', 0)),
            ('Retail Customers', data['summary'].get('retail_customers', 0)),
            ('Wholesale Customers', data['summary'].get('wholesale_customers', 0)),
            ('Active Customers', data['summary'].get('active_customers', 0)),
            ('Total Credit Limit', f"${data['summary'].get('total_credit_limit', 0)}"),
            ('Outstanding Balance', f"${data['summary'].get('total_outstanding_balance', 0)}"),
        ]
        
        story.extend(self._create_summary_table(summary_metrics, 'Customer Statistics'))
        
        # Aging summary
        aging_metrics = [
            ('Current (0-30 days)', f"${data['summary'].get('aging_current', 0)}"),
            ('31-60 days', f"${data['summary'].get('aging_31_60', 0)}"),
            ('61-90 days', f"${data['summary'].get('aging_61_90', 0)}"),
            ('Over 90 days', f"${data['summary'].get('aging_over_90', 0)}"),
            ('Total Overdue', f"${data['summary'].get('total_overdue', 0)}"),
        ]
        
        story.extend(self._create_summary_table(aging_metrics, 'Aging Analysis'))
        
        # Customer details (limit to 40 for PDF)
        if data.get('customers'):
            story.append(Paragraph('Customer Details (Top 40)', self.styles['SectionHeader']))
            
            headers = ['Name', 'Type', 'Credit Limit', 'Outstanding', 'Available', 'Status']
            table_data = [headers]
            
            for customer in data['customers'][:40]:
                table_data.append([
                    self._format_value(customer.get('name', ''))[:25],
                    self._format_value(customer.get('customer_type', '')),
                    f"${self._format_value(customer.get('credit_limit', ''))}",
                    f"${self._format_value(customer.get('outstanding_balance', ''))}",
                    f"${self._format_value(customer.get('available_credit', ''))}",
                    'Blocked' if customer.get('credit_blocked') else 'Active',
                ])
            
            customer_table = Table(table_data, repeatRows=1)
            customer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            
            story.append(customer_table)
            
            if len(data['customers']) > 40:
                story.append(Spacer(1, 10))
                story.append(Paragraph(
                    f'Showing 40 of {len(data["customers"])} customers. Use Excel or CSV export for complete data.',
                    self.styles['Italic']
                ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.read()


class InventoryPDFExporter(BasePDFExporter):
    """PDF exporter for inventory data"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export inventory data to PDF format"""
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        story = []
        
        # Header
        generated_at = data['summary'].get('export_date', timezone.now().strftime('%Y-%m-%d'))
        story.append(self._create_header_table('Inventory Export Report', generated_at))
        story.append(Spacer(1, 20))
        
        # Summary metrics
        summary_metrics = [
            ('Total Unique Products', data['summary'].get('total_unique_products', 0)),
            ('Total Quantity in Stock', data['summary'].get('total_quantity_in_stock', 0)),
            ('Total Inventory Value', f"${data['summary'].get('total_inventory_value', 0)}"),
            ('Out of Stock Items', data['summary'].get('out_of_stock_items', 0)),
            ('Low Stock Items', data['summary'].get('low_stock_items', 0)),
            ('In Stock Items', data['summary'].get('in_stock_items', 0)),
        ]
        
        story.extend(self._create_summary_table(summary_metrics, 'Inventory Statistics'))
        
        # Stock items (limit to 50 for PDF)
        if data.get('stock_items'):
            story.append(Paragraph('Stock Items (Top 50)', self.styles['SectionHeader']))
            
            headers = ['Product', 'SKU', 'Storefront', 'Qty', 'Cost', 'Price', 'Value', 'Status']
            table_data = [headers]
            
            for item in data['stock_items'][:50]:
                table_data.append([
                    self._format_value(item.get('product_name', ''))[:30],
                    self._format_value(item.get('sku', ''))[:15],
                    self._format_value(item.get('storefront', ''))[:15],
                    self._format_value(item.get('quantity_in_stock', 0)),
                    f"${self._format_value(item.get('unit_cost', ''))}",
                    f"${self._format_value(item.get('selling_price', ''))}",
                    f"${self._format_value(item.get('total_value', ''))}",
                    self._format_value(item.get('stock_status', '')),
                ])
            
            inventory_table = Table(table_data, repeatRows=1)
            inventory_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            
            story.append(inventory_table)
            
            if len(data['stock_items']) > 50:
                story.append(Spacer(1, 10))
                story.append(Paragraph(
                    f'Showing 50 of {len(data["stock_items"])} items. Use Excel or CSV export for complete data.',
                    self.styles['Italic']
                ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.read()


class AuditLogPDFExporter(BasePDFExporter):
    """PDF exporter for audit log data"""
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """Export audit logs to PDF format"""
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=0.5*inch,
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        story = []
        
        # Header
        generated_at = data['summary'].get('export_date', timezone.now().strftime('%Y-%m-%d'))
        story.append(self._create_header_table('Audit Log Export Report', generated_at))
        story.append(Spacer(1, 20))
        
        # Summary metrics
        summary_metrics = [
            ('Total Events', data['summary'].get('total_events', 0)),
            ('Date Range', f"{data['summary'].get('date_range_start', '')} to {data['summary'].get('date_range_end', '')}"),
            ('Unique Users', data['summary'].get('unique_users', 0)),
            ('Unique Event Types', data['summary'].get('unique_event_types', 0)),
            ('First Event', data['summary'].get('first_event_time', '')),
            ('Last Event', data['summary'].get('last_event_time', '')),
        ]
        
        story.extend(self._create_summary_table(summary_metrics, 'Audit Statistics'))
        
        # Event type breakdown
        story.append(Paragraph('Top Event Types', self.styles['SectionHeader']))
        event_data = [['Event Type', 'Count']]
        
        idx = 1
        while f'event_{idx}_type' in data['summary']:
            event_data.append([
                data['summary'][f'event_{idx}_type'],
                str(data['summary'][f'event_{idx}_count'])
            ])
            idx += 1
            if idx > 10:  # Limit to top 10
                break
        
        event_table = Table(event_data, colWidths=[5*inch, 2*inch])
        event_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        
        story.append(event_table)
        story.append(Spacer(1, 15))
        
        # Audit logs (limit to 40 for PDF)
        if data.get('audit_logs'):
            story.append(Paragraph('Audit Logs (Top 40)', self.styles['SectionHeader']))
            
            headers = ['Timestamp', 'Event', 'User', 'Entity', 'Description']
            table_data = [headers]
            
            for log in data['audit_logs'][:40]:
                table_data.append([
                    self._format_value(log.get('timestamp', ''))[:19],
                    self._format_value(log.get('event_label', ''))[:20],
                    self._format_value(log.get('user_name', ''))[:20],
                    self._format_value(log.get('entity_name', ''))[:20],
                    self._format_value(log.get('description', ''))[:40],
                ])
            
            audit_table = Table(table_data, repeatRows=1)
            audit_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            
            story.append(audit_table)
            
            if len(data['audit_logs']) > 40:
                story.append(Spacer(1, 10))
                story.append(Paragraph(
                    f'Showing 40 of {len(data["audit_logs"])} events. Use Excel or CSV export for complete data.',
                    self.styles['Italic']
                ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.read()
