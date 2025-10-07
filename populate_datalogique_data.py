"""
Comprehensive Data Population Script for DataLogique Systems
Generates realistic business data from January - October 2025

Features:
- Stock receipts with proper timing
- Sales (walk-in and business customers)
- Inventory adjustments (damage, spoilage, shrinkage)
- Credit sales with late payments
- Multiple payment methods
- Realistic date consistency
- Progressive monthly data
"""

import os
import django
import sys
from decimal import Decimal
from datetime import datetime, timedelta
import random

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from inventory.models import (
    Product, Category, StoreFront, Warehouse, Stock, StockProduct
)
from inventory.stock_adjustments import StockAdjustment
from sales.models import Sale, SaleItem, Payment, Customer
from django.db import transaction

User = get_user_model()

# Configuration
BUSINESS_NAME = "DataLogique Systems"
MONTHS = [
    (2025, 1, "January"),
    (2025, 2, "February"),
    (2025, 3, "March"),
    (2025, 4, "April"),
    (2025, 5, "May"),
    (2025, 6, "June"),
    (2025, 7, "July"),
    (2025, 8, "August"),
    (2025, 9, "September"),
    (2025, 10, "October"),
]

# Product categories and items
PRODUCT_CATEGORIES = {
    "Electronics": [
        ("Laptop HP ProBook", 2500.00, 3200.00),
        ("Desktop Dell OptiPlex", 1800.00, 2400.00),
        ("Monitor Samsung 24\"", 250.00, 350.00),
        ("Keyboard Logitech", 35.00, 55.00),
        ("Mouse Wireless", 25.00, 40.00),
        ("USB Flash Drive 32GB", 15.00, 25.00),
        ("External HDD 1TB", 80.00, 120.00),
        ("Printer HP LaserJet", 450.00, 650.00),
    ],
    "Office Supplies": [
        ("A4 Paper Ream", 8.50, 12.00),
        ("Stapler Heavy Duty", 15.00, 22.00),
        ("Pen Box (50pcs)", 12.00, 18.00),
        ("Marker Set", 8.00, 13.00),
        ("File Folder Box", 25.00, 35.00),
        ("Calculator Casio", 18.00, 28.00),
        ("Sticky Notes Pack", 5.00, 8.00),
        ("Highlighter Set", 6.00, 10.00),
    ],
    "Networking": [
        ("Router TP-Link", 65.00, 95.00),
        ("Network Switch 8-port", 85.00, 125.00),
        ("Ethernet Cable Cat6 (100m)", 45.00, 70.00),
        ("WiFi Adapter USB", 22.00, 35.00),
        ("Network Cabinet", 180.00, 260.00),
        ("Patch Panel 24-port", 55.00, 85.00),
    ],
    "Software": [
        ("Antivirus License 1yr", 45.00, 75.00),
        ("MS Office 2021", 180.00, 250.00),
        ("Adobe Creative Suite", 320.00, 450.00),
        ("Windows 11 Pro", 200.00, 280.00),
    ],
}

# Customer types
CUSTOMER_TYPES = ["WALK_IN", "BUSINESS", "WHOLESALER", "RETAILER"]

# Payment methods
PAYMENT_METHODS = ["CASH", "MOMO", "CARD", "CREDIT", "BANK_TRANSFER"]

# Adjustment reasons
ADJUSTMENT_REASONS = {
    "DAMAGE": ["Water damage", "Physical damage", "Shipping damage", "Handling damage"],
    "SPOILAGE": ["Expired", "Deteriorated", "Contaminated"],
    "SHRINKAGE": ["Theft suspected", "Missing items", "Unaccounted loss"],
    "RETURN": ["Customer return", "Supplier return", "Defective return"],
}


def get_random_date(year, month, exclude_dates=None):
    """Get random datetime for a given month, excluding certain dates"""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    
    while True:
        day = random.randint(1, last_day)
        hour = random.randint(8, 18)  # Business hours
        minute = random.randint(0, 59)
        
        dt = timezone.make_aware(datetime(year, month, day, hour, minute))
        
        if exclude_dates is None or dt.date() not in exclude_dates:
            return dt
    

def get_business_and_user():
    """Get or create DataLogique Systems business and owner"""
    business = Business.objects.filter(name=BUSINESS_NAME).first()
    
    if not business:
        # Get Mike Tetteh
        user = User.objects.filter(email="juliustetteh@gmail.com").first()
        if not user:
            print("❌ User Mike Tetteh not found!")
            return None, None
            
        # Create business
        business = Business.objects.create(
            name=BUSINESS_NAME,
            owner=user,
            email="info@datalogiquesystems.com",
            phone="+233244123456",
            address="123 Tech Avenue, Accra",
            business_type="RETAIL"
        )
        business.members.add(user)
        print(f"✅ Created business: {BUSINESS_NAME}")
    
    user = business.owner
    return business, user


def create_categories_and_products(business):
    """Create product categories and products"""
    products = []
    
    for category_name, items in PRODUCT_CATEGORIES.items():
        category, created = Category.objects.get_or_create(
            name=category_name,
            business=business,
            defaults={"description": f"{category_name} products"}
        )
        
        for product_name, cost, price in items:
            product, created = Product.objects.get_or_create(
                business=business,
                name=product_name,
                defaults={
                    "category": category,
                    "sku": f"SKU-{random.randint(10000, 99999)}",
                    "cost_price": Decimal(str(cost)),
                    "selling_price": Decimal(str(price)),
                    "unit": "piece",
                    "track_inventory": True,
                }
            )
            products.append(product)
    
    return products


def create_customers(business):
    """Create various customer types"""
    customers = []
    
    # Walk-in customer (default)
    walk_in, _ = Customer.objects.get_or_create(
        business=business,
        name="Walk-in",
        defaults={"customer_type": "WALK_IN"}
    )
    customers.append(walk_in)
    
    # Business customers
    business_customers = [
        ("Tech Solutions Ltd", "tech@solutions.com", "+233244111111", "BUSINESS"),
        ("Office Mart Ghana", "sales@officemart.gh", "+233244222222", "BUSINESS"),
        ("Digital World", "info@digitalworld.com", "+233244333333", "RETAILER"),
        ("Campus Supplies", "orders@campussupplies.com", "+233244444444", "WHOLESALER"),
        ("Smart Office Ltd", "contact@smartoffice.gh", "+233244555555", "BUSINESS"),
    ]
    
    for name, email, phone, ctype in business_customers:
        customer, _ = Customer.objects.get_or_create(
            business=business,
            name=name,
            defaults={
                "email": email,
                "phone": phone,
                "customer_type": ctype,
            }
        )
        customers.append(customer)
    
    return customers


def get_storefront(business):
    """Get or create default storefront"""
    storefront, _ = Storefront.objects.get_or_create(
        business=business,
        name="Main Store",
        defaults={
            "address": "123 Tech Avenue, Accra",
            "phone": "+233244123456",
            "is_active": True,
        }
    )
    return storefront


def generate_stock_receipt(business, storefront, products, receipt_date, user):
    """Generate stock receipt for products"""
    # Select random products to restock
    num_products = random.randint(3, 8)
    selected_products = random.sample(products, min(num_products, len(products)))
    
    for product in selected_products:
        quantity = random.randint(10, 100)
        
        # Update or create stock level
        stock_level, _ = StockLevel.objects.get_or_create(
            product=product,
            storefront=storefront,
            defaults={"quantity": 0}
        )
        
        old_quantity = stock_level.quantity
        stock_level.quantity += quantity
        stock_level.save()
        
        # Create stock movement
        StockMovement.objects.create(
            product=product,
            storefront=storefront,
            movement_type="IN",
            quantity=quantity,
            reference=f"STOCK-{receipt_date.strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            created_at=receipt_date,
            created_by=user,
        )
        
        print(f"  📦 Stocked {quantity} x {product.name} (Total: {stock_level.quantity})")


def generate_adjustments(business, storefront, products, month_start, month_end, user):
    """Generate inventory adjustments (damage, spoilage, shrinkage)"""
    adjustments = []
    
    # Get products with stock
    stocked_products = []
    for product in products:
        stock = StockLevel.objects.filter(product=product, storefront=storefront).first()
        if stock and stock.quantity > 0:
            stocked_products.append((product, stock))
    
    if not stocked_products:
        return adjustments
    
    # Generate 2-5 random adjustments per month
    num_adjustments = random.randint(2, 5)
    
    for _ in range(num_adjustments):
        product, stock = random.choice(stocked_products)
        
        # Random adjustment type
        adj_type = random.choice(["DAMAGE", "SPOILAGE", "SHRINKAGE"])
        reason = random.choice(ADJUSTMENT_REASONS[adj_type])
        
        # Adjustment quantity (1-10% of stock)
        max_qty = max(1, int(stock.quantity * 0.1))
        quantity = random.randint(1, max_qty)
        
        # Random date in month
        adj_date = get_random_date(month_start.year, month_start.month)
        
        # Ensure adjustment date is after stock was received
        # Get latest stock movement before this date
        latest_movement = StockMovement.objects.filter(
            product=product,
            storefront=storefront,
            movement_type="IN",
            created_at__lt=adj_date
        ).order_by('-created_at').first()
        
        if not latest_movement:
            continue  # Skip if no stock received before this date
        
        # Create adjustment
        adjustment = StockAdjustment.objects.create(
            product=product,
            storefront=storefront,
            adjustment_type=adj_type,
            quantity=quantity,
            reason=reason,
            created_at=adj_date,
            created_by=user,
        )
        
        # Update stock
        stock.quantity = max(0, stock.quantity - quantity)
        stock.save()
        
        adjustments.append(adjustment)
        print(f"  ⚠️  {adj_type}: -{quantity} x {product.name} ({reason})")
    
    return adjustments


def generate_sale(business, storefront, products, customers, sale_date, user):
    """Generate a single sale"""
    # Select customer
    customer = random.choice(customers)
    
    # Determine sale type and payment method
    if customer.customer_type == "WALK_IN":
        sale_type = "RETAIL"
        payment_type = random.choice(["CASH", "MOMO", "CARD"])
    else:
        sale_type = random.choice(["RETAIL", "WHOLESALE"])
        payment_type = random.choice(["CASH", "MOMO", "CARD", "CREDIT", "BANK_TRANSFER"])
    
    # Create sale
    receipt_number = f"REC-{sale_date.strftime('%Y%m')}-{random.randint(10000, 99999)}"
    
    sale = Sale.objects.create(
        business=business,
        storefront=storefront,
        customer=customer,
        sale_type=sale_type,
        payment_type=payment_type,
        receipt_number=receipt_number,
        status="DRAFT",
        created_at=sale_date,
        created_by=user,
    )
    
    # Add 1-5 random products
    num_items = random.randint(1, 5)
    selected_products = random.sample(products, min(num_items, len(products)))
    
    total_amount = Decimal('0.00')
    can_complete = True
    
    for product in selected_products:
        # Check stock
        stock = StockLevel.objects.filter(product=product, storefront=storefront).first()
        
        if not stock or stock.quantity == 0:
            can_complete = False
            continue
        
        # Check if stock was available at sale date
        # Get total stock movements before sale date
        stock_in = StockMovement.objects.filter(
            product=product,
            storefront=storefront,
            movement_type="IN",
            created_at__lte=sale_date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        stock_out = StockMovement.objects.filter(
            product=product,
            storefront=storefront,
            movement_type="OUT",
            created_at__lt=sale_date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        available = stock_in - stock_out
        
        if available <= 0:
            can_complete = False
            continue
        
        quantity = random.randint(1, min(5, int(available)))
        unit_price = product.selling_price
        
        # Apply discount for wholesale
        if sale_type == "WHOLESALE":
            discount_percent = random.uniform(5, 15)
            unit_price = unit_price * Decimal(str(1 - discount_percent / 100))
        
        subtotal = unit_price * quantity
        
        # Create sale item
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=subtotal,
        )
        
        total_amount += subtotal
    
    if sale.sale_items.count() == 0:
        sale.delete()
        return None
    
    # Update sale totals
    sale.subtotal = total_amount
    sale.total_amount = total_amount
    sale.save()
    
    # Complete sale if not credit
    if can_complete and payment_type != "CREDIT":
        # Create payment
        Payment.objects.create(
            sale=sale,
            amount=total_amount,
            payment_method=payment_type,
            payment_date=sale_date,
            created_by=user,
        )
        
        sale.amount_paid = total_amount
        sale.amount_due = Decimal('0.00')
        sale.status = "COMPLETED"
        sale.completed_at = sale_date
        sale.save()
        
        # Update stock and create movements
        for item in sale.sale_items.all():
            stock = StockLevel.objects.get(product=item.product, storefront=storefront)
            stock.quantity -= item.quantity
            stock.save()
            
            StockMovement.objects.create(
                product=item.product,
                storefront=storefront,
                movement_type="OUT",
                quantity=item.quantity,
                reference=receipt_number,
                created_at=sale_date,
                created_by=user,
            )
        
        print(f"  💰 Sale {receipt_number}: ${total_amount} ({payment_type}) - COMPLETED")
    
    elif payment_type == "CREDIT":
        # Partial or pending payment
        if random.random() < 0.7:  # 70% partial payment
            partial_amount = total_amount * Decimal(str(random.uniform(0.3, 0.7)))
            
            Payment.objects.create(
                sale=sale,
                amount=partial_amount,
                payment_method=random.choice(["CASH", "MOMO", "CARD"]),
                payment_date=sale_date,
                created_by=user,
            )
            
            sale.amount_paid = partial_amount
            sale.amount_due = total_amount - partial_amount
            sale.status = "PARTIAL"
        else:  # 30% full credit
            sale.amount_paid = Decimal('0.00')
            sale.amount_due = total_amount
            sale.status = "PENDING"
        
        sale.completed_at = sale_date
        sale.save()
        
        # Update stock and create movements
        for item in sale.sale_items.all():
            stock = StockLevel.objects.get(product=item.product, storefront=storefront)
            stock.quantity -= item.quantity
            stock.save()
            
            StockMovement.objects.create(
                product=item.product,
                storefront=storefront,
                movement_type="OUT",
                quantity=item.quantity,
                reference=receipt_number,
                created_at=sale_date,
                created_by=user,
            )
        
        print(f"  💳 Sale {receipt_number}: ${total_amount} (CREDIT) - {sale.status}")
        
        # Generate late payment (30% chance)
        if random.random() < 0.3 and sale.amount_due > 0:
            # Payment 5-15 days later
            days_late = random.randint(5, 15)
            payment_date = sale_date + timedelta(days=days_late)
            
            # If payment date is still within current time
            if payment_date <= timezone.now():
                payment_amount = sale.amount_due
                
                Payment.objects.create(
                    sale=sale,
                    amount=payment_amount,
                    payment_method=random.choice(["CASH", "MOMO", "BANK_TRANSFER"]),
                    payment_date=payment_date,
                    created_by=user,
                )
                
                sale.amount_paid += payment_amount
                sale.amount_due = Decimal('0.00')
                sale.status = "COMPLETED"
                sale.save()
                
                print(f"    ✅ Late payment: ${payment_amount} ({days_late} days late)")
    
    else:
        sale.status = "DRAFT"
        sale.save()
        print(f"  📝 Draft sale {receipt_number}: ${total_amount}")
    
    return sale


def generate_monthly_data(business, storefront, products, customers, year, month, month_name, user):
    """Generate all data for a specific month"""
    print(f"\n{'='*80}")
    print(f"📅 {month_name} {year}")
    print('='*80)
    
    month_start = timezone.make_aware(datetime(year, month, 1))
    
    # Calculate month end
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    month_end = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))
    
    # 1. Stock receipts (2-4 times per month)
    print("\n📦 Stock Receipts:")
    num_receipts = random.randint(2, 4)
    receipt_dates = []
    
    for i in range(num_receipts):
        receipt_date = get_random_date(year, month)
        receipt_dates.append(receipt_date.date())
        print(f"\n  Date: {receipt_date.strftime('%Y-%m-%d %H:%M')}")
        generate_stock_receipt(business, storefront, products, receipt_date, user)
    
    # 2. Generate sales (15-30 sales per month)
    print(f"\n💰 Sales:")
    num_sales = random.randint(15, 30)
    
    for _ in range(num_sales):
        sale_date = get_random_date(year, month)
        generate_sale(business, storefront, products, customers, sale_date, user)
    
    # 3. Adjustments (after stock receipts)
    print(f"\n⚠️  Inventory Adjustments:")
    generate_adjustments(business, storefront, products, month_start, month_end, user)
    
    # Summary
    total_sales = Sale.objects.filter(
        business=business,
        created_at__gte=month_start,
        created_at__lte=month_end
    )
    
    completed_sales = total_sales.filter(status="COMPLETED")
    total_revenue = completed_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    print(f"\n📊 {month_name} Summary:")
    print(f"  Total Sales: {total_sales.count()}")
    print(f"  Completed: {completed_sales.count()}")
    print(f"  Revenue: ${total_revenue:,.2f}")


@transaction.atomic
def main():
    """Main execution"""
    print("="*80)
    print("🚀 DATALOGIQUE SYSTEMS - COMPREHENSIVE DATA GENERATION")
    print("="*80)
    
    # Get business and user
    business, user = get_business_and_user()
    if not business:
        return
    
    print(f"\n✅ Business: {business.name}")
    print(f"✅ Owner: {user.email}")
    
    # Create products
    print(f"\n📦 Creating products...")
    products = create_categories_and_products(business)
    print(f"✅ Created {len(products)} products")
    
    # Create customers
    print(f"\n👥 Creating customers...")
    customers = create_customers(business)
    print(f"✅ Created {len(customers)} customers")
    
    # Get storefront
    storefront = get_storefront(business)
    print(f"✅ Storefront: {storefront.name}")
    
    # Generate data for each month
    for year, month, month_name in MONTHS:
        generate_monthly_data(business, storefront, products, customers, year, month, month_name, user)
    
    # Final summary
    print(f"\n{'='*80}")
    print("📈 FINAL SUMMARY")
    print('='*80)
    
    total_sales = Sale.objects.filter(business=business)
    completed = total_sales.filter(status="COMPLETED")
    pending = total_sales.filter(status="PENDING")
    partial = total_sales.filter(status="PARTIAL")
    draft = total_sales.filter(status="DRAFT")
    
    total_revenue = completed.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    print(f"\nSales Statistics:")
    print(f"  Total Sales: {total_sales.count()}")
    print(f"  ✅ Completed: {completed.count()} (${completed.aggregate(total=Sum('total_amount'))['total'] or 0:,.2f})")
    print(f"  ⏳ Pending: {pending.count()} (${pending.aggregate(total=Sum('total_amount'))['total'] or 0:,.2f})")
    print(f"  💰 Partial: {partial.count()} (${partial.aggregate(total=Sum('amount_due'))['total'] or 0:,.2f} due)")
    print(f"  📝 Draft: {draft.count()}")
    
    print(f"\n💵 Total Revenue (Completed): ${total_revenue:,.2f}")
    
    # Stock summary
    print(f"\n📦 Current Stock Levels:")
    for product in products[:10]:  # Show first 10
        stock = StockLevel.objects.filter(product=product, storefront=storefront).first()
        qty = stock.quantity if stock else 0
        print(f"  {product.name}: {qty} units")
    
    print(f"\n{'='*80}")
    print("✅ DATA GENERATION COMPLETE!")
    print('='*80)


if __name__ == "__main__":
    from django.db.models import Sum
    main()
