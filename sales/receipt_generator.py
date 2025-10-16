"""
Receipt/Invoice HTML and PDF generation utilities
"""
from decimal import Decimal
from typing import Dict, Any


def generate_receipt_html(receipt_data: Dict[str, Any]) -> str:
    """
    Generate HTML for a receipt that can be printed or converted to PDF.
    
    Args:
        receipt_data: Dictionary containing receipt information from ReceiptSerializer
        
    Returns:
        HTML string ready for printing or PDF conversion
    """
    
    # Get currency settings from business settings
    currency_symbol = '₵'  # Default to Ghanaian Cedi
    try:
        business_settings = receipt_data.get('business_settings', {})
        if business_settings:
            regional_settings = business_settings.get('regional', {})
            currency_info = regional_settings.get('currency', {})
            currency_symbol = currency_info.get('symbol', '₵')
    except (KeyError, TypeError, AttributeError):
        # Fall back to default if settings not available
        pass
    
    # Helper to format currency
    def format_currency(amount):
        if isinstance(amount, (int, float, Decimal)):
            return f"{currency_symbol} {float(amount):.2f}"
        return f"{currency_symbol} {amount}"
    
    # Determine if this is a wholesale sale
    is_wholesale = receipt_data.get('type') == 'WHOLESALE'
    sale_type_badge = ''
    if is_wholesale:
        sale_type_badge = '''
        <div class="sale-type-badge wholesale">
            ⚠️ WHOLESALE SALE ⚠️
        </div>
        '''
    else:
        sale_type_badge = '''
        <div class="sale-type-badge retail">
            🛒 RETAIL SALE
        </div>
        '''
    
    # Build line items HTML
    line_items_html = ''
    for item in receipt_data.get('line_items', []):
        qty = item.get('quantity', 0)
        unit_price = item.get('unit_price', 0)
        total_price = item.get('total_price', 0)
        discount = item.get('discount_amount', 0)
        
        pricing_note = f"(Wholesale)" if is_wholesale else ""
        
        line_items_html += f'''
        <tr class="line-item">
            <td class="item-name">{item.get('product_name', 'Unknown Product')}</td>
            <td class="item-qty">{qty}</td>
            <td class="item-price">{format_currency(unit_price)}</td>
            <td class="item-total">{format_currency(total_price)}</td>
        </tr>
        '''
        
        # Add SKU and pricing note as subrow
        line_items_html += f'''
        <tr class="line-item-detail">
            <td colspan="4">
                <small class="text-muted">SKU: {item.get('sku', 'N/A')}</small>
                {f'<small class="pricing-note">{pricing_note}</small>' if pricing_note else ''}
            </td>
        </tr>
        '''
        
        # Show discount if applicable
        if discount and float(discount) > 0:
            line_items_html += f'''
            <tr class="line-item-discount">
                <td colspan="3" class="text-right"><small>Item Discount:</small></td>
                <td class="discount-amount">-{format_currency(discount)}</td>
            </tr>
            '''
    
    # Get business phone number (may be array)
    business_phones = receipt_data.get('business_phone_numbers', [])
    business_phone = business_phones[0] if business_phones else 'N/A'
    
    # Customer information section
    customer_section = ''
    customer_name = receipt_data.get('customer_name')
    if customer_name:
        customer_phone = receipt_data.get('customer_phone', '')
        customer_email = receipt_data.get('customer_email', '')
        customer_type = receipt_data.get('customer_type', '')
        
        customer_section = f'''
        <div class="customer-section">
            <div class="info-row">
                <span class="label">Customer:</span>
                <span class="value">{customer_name}</span>
                {f'<span class="badge">{customer_type}</span>' if customer_type else ''}
            </div>
        '''
        
        if customer_phone:
            customer_section += f'''
            <div class="info-row">
                <span class="label">Phone:</span>
                <span class="value">{customer_phone}</span>
            </div>
            '''
        
        if customer_email:
            customer_section += f'''
            <div class="info-row">
                <span class="label">Email:</span>
                <span class="value">{customer_email}</span>
            </div>
            '''
        
        customer_section += '</div>'
    else:
        customer_section = '''
        <div class="customer-section">
            <div class="info-row">
                <span class="label">Customer:</span>
                <span class="value">Walk-in Customer</span>
            </div>
        </div>
        '''
    
    # Payment details
    change_given = receipt_data.get('change_given', 0)
    change_row = ''
    if change_given and float(change_given) > 0:
        change_row = f'''
        <tr class="change-row">
            <td colspan="3" class="text-right"><strong>Change:</strong></td>
            <td class="amount">{format_currency(change_given)}</td>
        </tr>
        '''
    
    # Amount due (for credit sales)
    amount_due = receipt_data.get('amount_due', 0)
    payment_type = receipt_data.get('payment_type', 'CASH')
    is_credit_sale = payment_type == 'CREDIT'
    
    amount_due_row = ''
    if float(amount_due) > 0:
        amount_due_row = f'''
        <tr class="amount-due-row">
            <td colspan="3" class="text-right"><strong>AMOUNT DUE:</strong></td>
            <td class="amount text-danger"><strong>{format_currency(amount_due)}</strong></td>
        </tr>
        '''
    
    # CREDIT SALE banner (displayed prominently if credit sale)
    credit_banner = ''
    if is_credit_sale and float(amount_due) > 0:
        credit_banner = '''
        <div class="credit-sale-banner">
            <div class="credit-alert">
                <h2>⚠️ CREDIT SALE ⚠️</h2>
                <p class="credit-message">Payment on credit - Customer to pay later</p>
                <p class="credit-due">Amount Due: ''' + format_currency(amount_due) + '''</p>
            </div>
        </div>
        '''
    
    # Build complete HTML
    html = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Receipt #{receipt_data.get('receipt_number', 'N/A')}</title>
    <style>
        @media print {{
            body {{ margin: 0; padding: 0; }}
            .no-print {{ display: none !important; }}
            
            /* Ensure credit banner is visible when printed */
            .credit-sale-banner {{
                background: #f8d7da !important;
                border: 3px solid #dc3545 !important;
                padding: 15px !important;
                page-break-inside: avoid;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            
            .credit-alert h2,
            .credit-message,
            .credit-due {{
                color: #721c24 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
            max-width: 80mm;
            margin: 0 auto;
            padding: 10mm;
            background: white;
        }}
        
        .receipt-container {{
            background: white;
            padding: 10px;
        }}
        
        /* Header Section */
        .header {{
            text-align: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px dashed #333;
        }}
        
        .business-name {{
            font-size: 18px;
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        
        .storefront-name {{
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 3px;
        }}
        
        .business-info {{
            font-size: 11px;
            color: #333;
            line-height: 1.5;
        }}
        
        /* Sale Type Badge */
        .sale-type-badge {{
            text-align: center;
            padding: 8px;
            margin: 10px 0;
            font-weight: bold;
            border: 2px solid;
        }}
        
        .sale-type-badge.wholesale {{
            background: #fff3cd;
            border-color: #856404;
            color: #856404;
        }}
        
        .sale-type-badge.retail {{
            background: #d1ecf1;
            border-color: #0c5460;
            color: #0c5460;
        }}
        
        /* Credit Sale Banner */
        .credit-sale-banner {{
            background: #f8d7da;
            border: 3px solid #dc3545;
            padding: 15px;
            margin: 15px 0;
            text-align: center;
        }}
        
        .credit-alert {{
            color: #721c24;
        }}
        
        .credit-alert h2 {{
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        
        .credit-message {{
            font-size: 13px;
            margin-bottom: 8px;
            font-weight: bold;
        }}
        
        .credit-due {{
            font-size: 16px;
            font-weight: bold;
            margin-top: 8px;
            color: #dc3545;
        }}
        
        /* Receipt Info */
        .receipt-info {{
            margin: 15px 0;
            padding: 10px 0;
            border-top: 1px solid #ddd;
            border-bottom: 1px solid #ddd;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 3px;
        }}
        
        .label {{
            font-weight: bold;
        }}
        
        .badge {{
            background: #6c757d;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            margin-left: 5px;
        }}
        
        /* Customer Section */
        .customer-section {{
            margin: 10px 0;
            padding: 10px 0;
            border-bottom: 1px solid #ddd;
        }}
        
        /* Line Items */
        .items-section {{
            margin: 15px 0;
        }}
        
        .items-section h3 {{
            font-size: 14px;
            margin-bottom: 10px;
            padding-bottom: 5px;
            border-bottom: 2px solid #333;
        }}
        
        .items-table {{
            width: 100%;
            margin-bottom: 15px;
        }}
        
        .items-table th {{
            text-align: left;
            padding: 5px 0;
            border-bottom: 1px solid #333;
            font-size: 11px;
        }}
        
        .items-table th.text-right,
        .items-table td.text-right {{
            text-align: right;
        }}
        
        .line-item td {{
            padding: 5px 0;
            vertical-align: top;
        }}
        
        .line-item-detail td {{
            padding: 0 0 8px 0;
            font-size: 10px;
            color: #666;
        }}
        
        .item-name {{
            font-weight: bold;
        }}
        
        .item-qty, .item-price, .item-total {{
            text-align: right;
        }}
        
        .pricing-note {{
            margin-left: 10px;
            color: #856404;
            font-weight: bold;
        }}
        
        .line-item-discount td {{
            padding: 2px 0;
            font-size: 10px;
        }}
        
        .discount-amount {{
            color: #dc3545;
            text-align: right;
        }}
        
        /* Totals Section */
        .totals-section {{
            margin-top: 15px;
            border-top: 2px solid #333;
            padding-top: 10px;
        }}
        
        .totals-table {{
            width: 100%;
        }}
        
        .totals-table td {{
            padding: 3px 0;
        }}
        
        .totals-table .text-right {{
            text-align: right;
        }}
        
        .totals-table .amount {{
            text-align: right;
            min-width: 80px;
        }}
        
        .subtotal-row {{
            border-top: 1px solid #ddd;
            padding-top: 5px;
        }}
        
        .grand-total-row {{
            font-size: 14px;
            font-weight: bold;
            border-top: 2px solid #333;
            border-bottom: 2px solid #333;
            padding: 5px 0;
        }}
        
        .grand-total-row td {{
            padding: 8px 0;
        }}
        
        .amount-due-row {{
            color: #dc3545;
            font-weight: bold;
        }}
        
        /* Footer */
        .footer {{
            margin-top: 20px;
            padding-top: 15px;
            border-top: 2px dashed #333;
            text-align: center;
        }}
        
        .thank-you {{
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .footer-info {{
            font-size: 10px;
            color: #666;
        }}
        
        /* Utilities */
        .text-muted {{
            color: #666;
        }}
        
        .text-danger {{
            color: #dc3545;
        }}
        
        .text-right {{
            text-align: right;
        }}
    </style>
</head>
<body>
    <div class="receipt-container">
        <!-- Header -->
        <div class="header">
            <div class="business-name">{receipt_data.get('business_name', 'BUSINESS NAME')}</div>
            <div class="storefront-name">{receipt_data.get('storefront_name', 'Store')}</div>
            <div class="business-info">
                {receipt_data.get('business_address', 'N/A')}<br>
                Phone: {business_phone}<br>
                {f"Email: {receipt_data.get('business_email', '')}<br>" if receipt_data.get('business_email') else ''}
                TIN: {receipt_data.get('business_tin', 'N/A')}
            </div>
        </div>
        
        <!-- Sale Type Badge -->
        {sale_type_badge}
        
        <!-- CREDIT SALE Banner (if applicable) -->
        {credit_banner}
        
        <!-- Receipt Information -->
        <div class="receipt-info">
            <div class="info-row">
                <span class="label">Receipt #:</span>
                <span class="value">{receipt_data.get('receipt_number', 'N/A')}</span>
            </div>
            <div class="info-row">
                <span class="label">Date:</span>
                <span class="value">{receipt_data.get('completed_at_formatted', 'N/A')}</span>
            </div>
            <div class="info-row">
                <span class="label">Served by:</span>
                <span class="value">{receipt_data.get('served_by', 'Staff')}</span>
            </div>
            <div class="info-row">
                <span class="label">Payment:</span>
                <span class="value">{receipt_data.get('payment_type_display', 'N/A')}</span>
            </div>
        </div>
        
        <!-- Customer Information -->
        {customer_section}
        
        <!-- Line Items -->
        <div class="items-section">
            <h3>ITEMS</h3>
            <table class="items-table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th class="text-right">Qty</th>
                        <th class="text-right">Price</th>
                        <th class="text-right">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {line_items_html}
                </tbody>
            </table>
        </div>
        
        <!-- Totals -->
        <div class="totals-section">
            <table class="totals-table">
                <tr class="subtotal-row">
                    <td colspan="3" class="text-right">Subtotal:</td>
                    <td class="amount">{format_currency(receipt_data.get('subtotal', 0))}</td>
                </tr>
                {f'''
                <tr>
                    <td colspan="3" class="text-right">Discount:</td>
                    <td class="amount">-{format_currency(receipt_data.get('discount_amount', 0))}</td>
                </tr>
                ''' if float(receipt_data.get('discount_amount', 0)) > 0 else ''}
                {f'''
                <tr>
                    <td colspan="3" class="text-right">Tax:</td>
                    <td class="amount">{format_currency(receipt_data.get('tax_amount', 0))}</td>
                </tr>
                ''' if float(receipt_data.get('tax_amount', 0)) > 0 else ''}
                <tr class="grand-total-row">
                    <td colspan="3" class="text-right"><strong>TOTAL:</strong></td>
                    <td class="amount"><strong>{format_currency(receipt_data.get('total_amount', 0))}</strong></td>
                </tr>
                <tr>
                    <td colspan="3" class="text-right">Paid ({receipt_data.get('payment_type', 'CASH')}):</td>
                    <td class="amount">{format_currency(receipt_data.get('amount_paid', 0))}</td>
                </tr>
                {change_row}
                {amount_due_row}
            </table>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <div class="thank-you">Thank you for your business!</div>
            <div class="footer-info">
                Items: {receipt_data.get('total_items', 0)} | 
                Qty: {receipt_data.get('total_quantity', 0)}
            </div>
            {f'<div class="footer-info" style="margin-top: 10px;">This is a {receipt_data.get("type_display", "retail").upper()} sale receipt</div>'}
        </div>
    </div>
</body>
</html>
    '''
    
    return html


def generate_receipt_pdf(receipt_data: Dict[str, Any]) -> bytes:
    """
    Generate PDF receipt from receipt data.
    
    This is an optional feature that requires additional dependencies:
    - weasyprint or pdfkit
    
    Install with: pip install weasyprint
    
    Args:
        receipt_data: Dictionary containing receipt information from ReceiptSerializer
        
    Returns:
        PDF file as bytes
    """
    try:
        from weasyprint import HTML
        
        # Generate HTML
        html_content = generate_receipt_html(receipt_data)
        
        # Convert to PDF
        pdf_bytes = HTML(string=html_content).write_pdf()
        
        return pdf_bytes
        
    except ImportError:
        raise ImportError(
            "WeasyPrint is not installed. "
            "Install it with: pip install weasyprint"
        )
    except Exception as e:
        raise Exception(f"Failed to generate PDF: {str(e)}")
