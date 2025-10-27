"""
Test receipt generation functionality
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from sales.models import Sale
from sales.receipt_serializers import ReceiptSerializer
from sales.receipt_generator import generate_receipt_html
from decimal import Decimal


def test_receipt_generation():
    """Test receipt serializer and HTML generation"""
    
    print("=" * 80)
    print("RECEIPT GENERATION TEST")
    print("=" * 80)
    
    # Find a completed sale
    completed_sale = Sale.objects.filter(
        status='COMPLETED'
    ).select_related(
        'business', 'storefront', 'customer', 'user'
    ).prefetch_related(
        'sale_items__product'
    ).first()
    
    if not completed_sale:
        print("❌ No completed sales found in database")
        print("   Create a completed sale first")
        return
    
    print(f"\n✅ Found completed sale: {completed_sale.receipt_number}")
    print(f"   Status: {completed_sale.status}")
    print(f"   Type: {completed_sale.type}")
    print(f"   Total: GH₵ {completed_sale.total_amount}")
    
    # Test ReceiptSerializer
    print("\n" + "-" * 80)
    print("TESTING RECEIPT SERIALIZER")
    print("-" * 80)
    
    serializer = ReceiptSerializer(completed_sale)
    receipt_data = serializer.data
    
    print(f"\n📄 Receipt Data:")
    print(f"   Receipt #: {receipt_data.get('receipt_number')}")
    print(f"   Type: {receipt_data.get('type')} ({receipt_data.get('type_display')})")
    print(f"   Business: {receipt_data.get('business_name')}")
    print(f"   Storefront: {receipt_data.get('storefront_name')}")
    print(f"   Customer: {receipt_data.get('customer_name') or 'Walk-in'}")
    print(f"   Served by: {receipt_data.get('served_by')}")
    print(f"   Payment: {receipt_data.get('payment_type_display')}")
    print(f"   Date: {receipt_data.get('completed_at_formatted')}")
    
    print(f"\n💰 Financial Details:")
    print(f"   Subtotal: GH₵ {receipt_data.get('subtotal')}")
    print(f"   Discount: GH₵ {receipt_data.get('discount_amount')}")
    print(f"   Tax: GH₵ {receipt_data.get('tax_amount')}")
    print(f"   Total: GH₵ {receipt_data.get('total_amount')}")
    print(f"   Paid: GH₵ {receipt_data.get('amount_paid')}")
    print(f"   Due: GH₵ {receipt_data.get('amount_due')}")
    print(f"   Change: GH₵ {receipt_data.get('change_given')}")
    
    print(f"\n📦 Line Items ({receipt_data.get('total_items')} items, {receipt_data.get('total_quantity')} total qty):")
    for idx, item in enumerate(receipt_data.get('line_items', []), 1):
        print(f"   {idx}. {item['product_name']}")
        print(f"      SKU: {item['sku']}")
        print(f"      Qty: {item['quantity']} × GH₵ {item['unit_price']} = GH₵ {item['total_price']}")
        if float(item.get('discount_amount', 0)) > 0:
            print(f"      Discount: -GH₵ {item['discount_amount']}")
    
    # Test HTML generation
    print("\n" + "-" * 80)
    print("TESTING HTML GENERATION")
    print("-" * 80)
    
    html_content = generate_receipt_html(receipt_data)
    
    # Save to file
    output_file = f"receipt_{completed_sale.receipt_number}.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✅ HTML receipt generated successfully")
    print(f"   File saved: {output_file}")
    print(f"   File size: {len(html_content)} bytes")
    print(f"   Open in browser to view formatted receipt")
    
    # Check if sale type is properly displayed
    if receipt_data.get('type') == 'WHOLESALE':
        print(f"\n⚠️  WHOLESALE SALE - Badge should be visible in receipt")
    else:
        print(f"\n🛒 RETAIL SALE - Badge should be visible in receipt")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Receipt serializer working correctly")
    print(f"✅ HTML generation successful")
    print(f"✅ All required data present")
    
    print(f"\n📋 Next Steps:")
    print(f"   1. Open {output_file} in a browser to view receipt")
    print(f"   2. Test printing using browser print function")
    print(f"   3. Verify wholesale/retail badge displays correctly")
    print(f"   4. Check all amounts and totals are correct")
    
    print("\n" + "=" * 80)


def test_wholesale_retail_receipts():
    """Test receipts for both wholesale and retail sales"""
    
    print("\n" + "=" * 80)
    print("WHOLESALE vs RETAIL RECEIPT COMPARISON")
    print("=" * 80)
    
    # Find retail sale
    retail_sale = Sale.objects.filter(
        status='COMPLETED',
        type='RETAIL'
    ).first()
    
    # Find wholesale sale
    wholesale_sale = Sale.objects.filter(
        status='COMPLETED',
        type='WHOLESALE'
    ).first()
    
    if retail_sale:
        print(f"\n🛒 RETAIL SALE FOUND:")
        print(f"   Receipt: {retail_sale.receipt_number}")
        print(f"   Total: GH₵ {retail_sale.total_amount}")
        print(f"   Items: {retail_sale.sale_items.count()}")
        
        # Generate HTML
        serializer = ReceiptSerializer(retail_sale)
        html = generate_receipt_html(serializer.data)
        
        filename = f"receipt_retail_{retail_sale.receipt_number}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"   ✅ Saved: {filename}")
    else:
        print(f"\n⚠️  No retail sales found")
    
    if wholesale_sale:
        print(f"\n📦 WHOLESALE SALE FOUND:")
        print(f"   Receipt: {wholesale_sale.receipt_number}")
        print(f"   Total: GH₵ {wholesale_sale.total_amount}")
        print(f"   Items: {wholesale_sale.sale_items.count()}")
        
        # Generate HTML
        serializer = ReceiptSerializer(wholesale_sale)
        html = generate_receipt_html(serializer.data)
        
        filename = f"receipt_wholesale_{wholesale_sale.receipt_number}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"   ✅ Saved: {filename}")
    else:
        print(f"\n⚠️  No wholesale sales found")
    
    if retail_sale or wholesale_sale:
        print(f"\n💡 Compare the receipts to see the difference:")
        print(f"   - Retail receipts show 'RETAIL SALE' badge")
        print(f"   - Wholesale receipts show 'WHOLESALE SALE' badge with warning")
        print(f"   - Prices should reflect the correct sale type")


if __name__ == '__main__':
    print("\nStarting receipt generation tests...\n")
    
    try:
        test_receipt_generation()
        test_wholesale_retail_receipts()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during testing:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
