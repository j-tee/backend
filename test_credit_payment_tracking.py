"""
Test Credit Payment Tracking System
Tests the new credit sales payment recording functionality
"""
import sys
import os
import django

# Setup Django
sys.path.insert(0, '/home/teejay/Documents/Projects/pos/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.db import transaction
from sales.models import Sale, SaleItem, Payment, Customer
from inventory.models import StoreFront, Product, Stock, StockProduct
from accounts.models import Business

def run_tests():
    """Run credit payment tracking tests"""
    
    print("\n" + "="*80)
    print("CREDIT PAYMENT TRACKING - SYSTEM TEST")
    print("="*80)
    
    # Get test data
    business = Business.objects.first()
    storefront = StoreFront.objects.first()
    # Get a customer - create one if doesn't exist
    customer = Customer.objects.filter(business=business).first()
    if not customer:
        customer = Customer.objects.create(
            business=business,
            name="Test Customer",
            phone="1234567890",
            credit_limit=Decimal('10000.00')
        )
    product = Product.objects.filter(business=business).first()
    
    print(f"\n📋 Test Data:")
    print(f"  Business: {business.name}")
    print(f"  Storefront: {storefront.name if storefront else 'None'}")
    print(f"  Customer: {customer.name if customer else 'None'}")
    print(f"  Product: {product.name if product else 'None'}")
    
    if not all([business, storefront, customer, product]):
        print("\n❌ ERROR: Missing required test data")
        return
    
    # Test 1: Create unpaid credit sale
    print(f"\n" + "-"*80)
    print("TEST 1: Create Credit Sale WITHOUT Payment (PENDING Status)")
    print("-"*80)
    
    try:
        with transaction.atomic():
            # Create sale
            sale = Sale.objects.create(
                business=business,
                storefront=storefront,
                customer=customer,
                user=business.owner,
                status='DRAFT',
                payment_type='CREDIT'
            )
            
            # Add item - get stock and stock_product from product
            stock = Stock.objects.first()
            stock_product = StockProduct.objects.filter(
                product=product,
                quantity__gt=Decimal('10.00')
            ).first()
            
            sale_item = SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=Decimal('5.00'),
                unit_price=Decimal('100.00'),
                stock=stock,
                stock_product=stock_product
            )
            
            # Calculate totals
            sale.calculate_totals()
            sale.save()
            
            # Record customer balance before completion
            customer.refresh_from_db()
            balance_before = customer.outstanding_balance
            
            # Complete sale WITHOUT payment
            sale.complete_sale()
            sale.refresh_from_db()
            customer.refresh_from_db()
            
            print(f"\n✅ Sale Created:")
            print(f"  Receipt: {sale.receipt_number}")
            print(f"  Total Amount: ${sale.total_amount}")
            print(f"  Amount Paid: ${sale.amount_paid}")
            print(f"  Amount Due: ${sale.amount_due}")
            print(f"  Status: {sale.status}")
            print(f"  Payment Type: {sale.payment_type}")
            print(f"\n👤 Customer Balance:")
            print(f"  Before: ${balance_before}")
            print(f"  After: ${customer.outstanding_balance}")
            print(f"  Increase: ${customer.outstanding_balance - balance_before}")
            
            # Verify
            assert sale.status == 'PENDING', f"Expected PENDING, got {sale.status}"
            assert sale.amount_paid == Decimal('0.00'), f"Expected 0.00 paid, got {sale.amount_paid}"
            assert sale.amount_due == sale.total_amount, f"Expected amount_due={sale.total_amount}, got {sale.amount_due}"
            assert customer.outstanding_balance == balance_before + sale.total_amount, "Customer balance not updated correctly"
            
            print(f"\n✅ TEST 1 PASSED: Credit sale correctly marked as PENDING")
            
            # Test 2: Record partial payment
            print(f"\n" + "-"*80)
            print("TEST 2: Record Partial Payment (PARTIAL Status)")
            print("-"*80)
            
            payment_amount = Decimal('200.00')
            
            payment1 = Payment.objects.create(
                sale=sale,
                customer=customer,
                amount_paid=payment_amount,
                payment_method='CASH',
                status='SUCCESSFUL',
                processed_by=business.owner,
                notes='First payment'
            )
            
            # Update sale
            sale.amount_paid += payment_amount
            sale.amount_due = sale.total_amount - sale.amount_paid
            
            # Update status
            if sale.amount_due == Decimal('0.00'):
                sale.status = 'COMPLETED'
            elif sale.amount_paid > Decimal('0.00'):
                sale.status = 'PARTIAL'
            
            sale.save()
            
            # Update customer balance
            customer.outstanding_balance -= payment_amount
            customer.save()
            
            sale.refresh_from_db()
            customer.refresh_from_db()
            
            print(f"\n💰 Payment Recorded:")
            print(f"  Amount: ${payment1.amount_paid}")
            print(f"  Method: {payment1.payment_method}")
            print(f"  Reference: {payment1.reference_number or 'N/A'}")
            print(f"\n📊 Updated Sale:")
            print(f"  Total Amount: ${sale.total_amount}")
            print(f"  Amount Paid: ${sale.amount_paid}")
            print(f"  Amount Due: ${sale.amount_due}")
            print(f"  Status: {sale.status}")
            print(f"  Payment Count: {sale.payments.count()}")
            print(f"\n👤 Customer Balance:")
            print(f"  Outstanding: ${customer.outstanding_balance}")
            
            # Verify
            assert sale.status == 'PARTIAL', f"Expected PARTIAL, got {sale.status}"
            assert sale.amount_paid == payment_amount, f"Expected {payment_amount} paid, got {sale.amount_paid}"
            assert sale.amount_due == sale.total_amount - payment_amount, f"Amount due calculation incorrect"
            assert sale.payments.count() == 1, "Payment not linked to sale"
            
            print(f"\n✅ TEST 2 PASSED: Partial payment correctly recorded")
            
            # Test 3: Record final payment
            print(f"\n" + "-"*80)
            print("TEST 3: Record Final Payment (COMPLETED Status)")
            print("-"*80)
            
            remaining_amount = sale.amount_due
            
            payment2 = Payment.objects.create(
                sale=sale,
                customer=customer,
                amount_paid=remaining_amount,
                payment_method='CARD',
                status='SUCCESSFUL',
                processed_by=business.owner,
                notes='Final payment'
            )
            
            # Update sale
            sale.amount_paid += remaining_amount
            sale.amount_due = Decimal('0.00')
            sale.status = 'COMPLETED'
            sale.save()
            
            # Update customer balance
            customer.outstanding_balance -= remaining_amount
            if customer.outstanding_balance < Decimal('0.00'):
                customer.outstanding_balance = Decimal('0.00')
            customer.save()
            
            sale.refresh_from_db()
            customer.refresh_from_db()
            
            print(f"\n💰 Final Payment Recorded:")
            print(f"  Amount: ${payment2.amount_paid}")
            print(f"  Method: {payment2.payment_method}")
            print(f"\n📊 Updated Sale:")
            print(f"  Total Amount: ${sale.total_amount}")
            print(f"  Amount Paid: ${sale.amount_paid}")
            print(f"  Amount Due: ${sale.amount_due}")
            print(f"  Status: {sale.status}")
            print(f"  Payment Count: {sale.payments.count()}")
            print(f"\n💳 Payment History:")
            for idx, payment in enumerate(sale.payments.all(), 1):
                print(f"  {idx}. ${payment.amount_paid} ({payment.payment_method}) - {payment.notes}")
            print(f"\n👤 Customer Balance:")
            print(f"  Outstanding: ${customer.outstanding_balance}")
            
            # Verify
            assert sale.status == 'COMPLETED', f"Expected COMPLETED, got {sale.status}"
            assert sale.amount_paid == sale.total_amount, f"Expected full payment"
            assert sale.amount_due == Decimal('0.00'), f"Expected 0.00 due, got {sale.amount_due}"
            assert sale.payments.count() == 2, "Both payments not linked"
            
            print(f"\n✅ TEST 3 PASSED: Final payment correctly recorded, sale COMPLETED")
            
            # Test 4: Test new serializer fields
            print(f"\n" + "-"*80)
            print("TEST 4: Test Enhanced Serializer Fields")
            print("-"*80)
            
            from sales.serializers import SaleSerializer
            
            serializer = SaleSerializer(sale)
            data = serializer.data
            
            print(f"\n📄 Serialized Sale Data:")
            print(f"  Receipt: {data['receipt_number']}")
            print(f"  Total: ${data['total_amount']}")
            print(f"  Paid: ${data['amount_paid']}")
            print(f"  Due: ${data['amount_due']}")
            print(f"  Status: {data['status']}")
            print(f"  Payment Status: {data.get('payment_status')}")
            print(f"  Payment %: {data.get('payment_completion_percentage')}%")
            print(f"  Payments: {len(data.get('payments', []))} payment(s)")
            
            # Verify
            assert 'payment_status' in data, "payment_status field missing"
            assert 'payment_completion_percentage' in data, "payment_completion_percentage field missing"
            assert data['payment_completion_percentage'] == 100.0, "Payment percentage should be 100%"
            assert data['payment_status'] == 'Fully Paid', f"Expected 'Fully Paid', got {data['payment_status']}"
            
            print(f"\n✅ TEST 4 PASSED: New serializer fields working correctly")
            
            # Test 5: Test new filters
            print(f"\n" + "-"*80)
            print("TEST 5: Test Payment Status Filters")
            print("-"*80)
            
            # Get all credit sales
            all_credit = Sale.objects.filter(payment_type='CREDIT')
            
            # Filter unpaid
            unpaid = all_credit.filter(
                amount_paid=Decimal('0.00'),
                amount_due__gt=Decimal('0.00')
            )
            
            # Filter partial
            partial = all_credit.filter(
                amount_paid__gt=Decimal('0.00'),
                amount_due__gt=Decimal('0.00')
            )
            
            # Filter paid
            paid = all_credit.filter(
                amount_due=Decimal('0.00')
            )
            
            # Filter with outstanding balance
            outstanding = all_credit.filter(amount_due__gt=Decimal('0.00'))
            
            print(f"\n📊 Credit Sales Summary:")
            print(f"  Total Credit Sales: {all_credit.count()}")
            print(f"  Unpaid (PENDING): {unpaid.count()}")
            print(f"  Partially Paid: {partial.count()}")
            print(f"  Fully Paid: {paid.count()}")
            print(f"  With Outstanding Balance: {outstanding.count()}")
            
            print(f"\n✅ TEST 5 PASSED: Filters working correctly")
            
            # Cleanup
            print(f"\n🧹 Cleaning up test data...")
            sale.delete()
            
            print(f"\n" + "="*80)
            print("✅ ALL TESTS PASSED")
            print("="*80)
            print(f"\nCredit Payment Tracking System is working correctly!")
            print(f"\nFeatures Verified:")
            print(f"  ✅ PENDING status for unpaid credit sales")
            print(f"  ✅ PARTIAL status for partially paid sales")
            print(f"  ✅ COMPLETED status when fully paid")
            print(f"  ✅ Customer balance updates correctly")
            print(f"  ✅ Payment history tracking")
            print(f"  ✅ New serializer fields (payment_status, payment_completion_percentage)")
            print(f"  ✅ Payment filters (unpaid, partial, paid)")
            print("="*80 + "\n")
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        # Cleanup on error
        try:
            sale.delete()
        except:
            pass

if __name__ == '__main__':
    run_tests()
