#!/usr/bin/env python
"""
Quick data population script for development.
Creates essential test data while respecting stock quantity rules.
"""
import os
import sys
import django
from decimal import Decimal
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.utils import timezone
from accounts.models import User, Business, BusinessMembership
from inventory.models import (
    Category, Product, Warehouse, StoreFront, 
    BusinessWarehouse, BusinessStoreFront, Stock, StockProduct,
    StoreFrontInventory, Supplier
)
from sales.models import Customer

print("="*80)
print("🚀 POPULATING DATABASE WITH TEST DATA")
print("="*80)

# 1. Create/Get User
print("\n📝 Creating Users...")
user, created = User.objects.update_or_create(
    email='mikedit009@gmail.com',
    defaults={
        'name': 'Mike Edit',
        'email_verified': True,
        'is_active': True,
        'account_type': User.ACCOUNT_OWNER
    }
)
if created or not user.check_password('TestPass123!'):
    user.set_password('TestPass123!')
    user.save()
print(f"  ✅ User: {user.email}")

# 2. Create Business
print("\n🏢 Creating Business...")
business, created = Business.objects.get_or_create(
    owner=user,
    defaults={
        'name': 'Datalogique Ghana',
        'email': 'info@datalogique.com',
        'tin': 'TIN-DL-2024',
        'address': '123 Tech Street, Accra'
    }
)
print(f"  ✅ Business: {business.name}")

# 3. Create Business Membership
BusinessMembership.objects.get_or_create(
    user=user,
    business=business,
    defaults={
        'role': 'OWNER',
        'is_admin': True,
        'is_active': True
    }
)

# 4. Create Warehouse
print("\n🏭 Creating Warehouses...")
warehouse, created = Warehouse.objects.get_or_create(
    name='Main Warehouse - Accra',
    defaults={
        'location': 'Accra Industrial Area',
        'manager': user
    }
)
BusinessWarehouse.objects.get_or_create(
    business=business,
    warehouse=warehouse
)
print(f"  ✅ Warehouse: {warehouse.name}")

# 5. Create Storefronts
print("\n🏪 Creating Storefronts...")
storefronts = []
storefront_data = [
    ('Adenta Branch', 'Adenta, Accra'),
    ('Cow Lane Branch', 'Cow Lane, Accra'),
    ('Osu Branch', 'Osu, Accra'),
]

for name, location in storefront_data:
    storefront, created = StoreFront.objects.get_or_create(
        name=name,
        defaults={
            'location': location,
            'user': user
        }
    )
    BusinessStoreFront.objects.get_or_create(
        business=business,
        storefront=storefront
    )
    storefronts.append(storefront)
    print(f"  ✅ Storefront: {name}")

# 6. Create Categories
print("\n📦 Creating Categories...")
categories_data = [
    'Electronics',
    'Office Supplies',
    'Software',
    'Accessories',
    'Computers'
]

categories = {}
for cat_name in categories_data:
    category, created = Category.objects.get_or_create(
        name=cat_name
    )
    categories[cat_name] = category
print(f"  ✅ Created {len(categories)} categories")

# 7. Create Supplier
print("\n🚚 Creating Suppliers...")
supplier, created = Supplier.objects.get_or_create(
    business=business,
    name='Tech Distributors Ltd',
    defaults={
        'email': 'sales@techdist.com',
        'contact_person': 'John Doe'
    }
)
print(f"  ✅ Supplier: {supplier.name}")

# 8. Create Products
print("\n📱 Creating Products...")
products_data = [
    ('HP Laptop ProBook 450', 'LAP-HP-450', 'Computers', Decimal('2500.00'), Decimal('2800.00')),
    ('Dell Mouse Wireless', 'MOU-DELL-W', 'Accessories', Decimal('35.00'), Decimal('45.00')),
    ('Logitech Keyboard', 'KEY-LOG-001', 'Accessories', Decimal('85.00'), Decimal('110.00')),
    ('Samsung Monitor 24"', 'MON-SAM-24', 'Electronics', Decimal('450.00'), Decimal('550.00')),
    ('USB Flash Drive 32GB', 'USB-32GB', 'Accessories', Decimal('15.00'), Decimal('25.00')),
    ('A4 Paper Ream', 'PAPER-A4', 'Office Supplies', Decimal('25.00'), Decimal('35.00')),
    ('Printer HP LaserJet', 'PRT-HP-LJ', 'Electronics', Decimal('800.00'), Decimal('950.00')),
    ('HDMI Cable 2M', 'HDMI-2M', 'Accessories', Decimal('12.00'), Decimal('20.00')),
]

products = {}
for name, sku, cat_name, cost, retail in products_data:
    product, created = Product.objects.get_or_create(
        business=business,
        sku=sku,
        defaults={
            'name': name,
            'category': categories[cat_name],
        }
    )
    products[sku] = product
print(f"  ✅ Created {len(products)} products")

# 9. Create Stock (Initial Intake)
print("\n📦 Creating Initial Stock Intake...")
stock, created = Stock.objects.get_or_create(
    warehouse=warehouse,
    defaults={
        'description': 'Initial Stock - January 2025',
        'received_date': timezone.now().date() - timedelta(days=30),
        'supplier': supplier
    }
)

# 10. Create StockProducts (with initial quantities)
print("\n📊 Creating Stock Products...")
stock_data = [
    ('LAP-HP-450', 50, Decimal('2500.00'), Decimal('2800.00')),
    ('MOU-DELL-W', 100, Decimal('35.00'), Decimal('45.00')),
    ('KEY-LOG-001', 75, Decimal('85.00'), Decimal('110.00')),
    ('MON-SAM-24', 30, Decimal('450.00'), Decimal('550.00')),
    ('USB-32GB', 200, Decimal('15.00'), Decimal('25.00')),
    ('PAPER-A4', 150, Decimal('25.00'), Decimal('35.00')),
    ('PRT-HP-LJ', 20, Decimal('800.00'), Decimal('950.00')),
    ('HDMI-2M', 120, Decimal('12.00'), Decimal('20.00')),
]

stock_products = {}
for sku, qty, cost, retail in stock_data:
    sp, created = StockProduct.objects.get_or_create(
        product=products[sku],
        stock=stock,
        defaults={
            'quantity': qty,
            'unit_cost': cost,
            'retail_price': retail
        }
    )
    stock_products[sku] = sp
print(f"  ✅ Created {len(stock_products)} stock products")

# 11. Transfer Stock to Storefronts
print("\n🚚 Transferring Stock to Storefronts...")
# Distribute stock across storefronts
transfers = [
    (storefronts[0], 'LAP-HP-450', 15),  # Adenta: 15 laptops
    (storefronts[0], 'MOU-DELL-W', 30),  # Adenta: 30 mice
    (storefronts[0], 'USB-32GB', 50),    # Adenta: 50 USB drives
    
    (storefronts[1], 'LAP-HP-450', 10),  # Cow Lane: 10 laptops
    (storefronts[1], 'KEY-LOG-001', 20),  # Cow Lane: 20 keyboards
    (storefronts[1], 'HDMI-2M', 30),     # Cow Lane: 30 HDMI cables
    
    (storefronts[2], 'MON-SAM-24', 10),  # Osu: 10 monitors
    (storefronts[2], 'PAPER-A4', 40),    # Osu: 40 paper reams
    (storefronts[2], 'PRT-HP-LJ', 5),    # Osu: 5 printers
]

for storefront, sku, qty in transfers:
    StoreFrontInventory.objects.get_or_create(
        storefront=storefront,
        product=products[sku],
        defaults={
            'quantity': qty
        }
    )
print(f"  ✅ Transferred stock to {len(storefronts)} storefronts")

# 12. Create Customers
print("\n👥 Creating Customers...")
customers_data = [
    ('Walk-in Customer', 'walkin@datalogique.com', None),
    ('Tech Solutions Ltd', 'info@techsolutions.com', '0244123456'),
    ('Ghana Enterprises', 'contact@ghent.com', '0501234567'),
    ('Digital Marketing Co', 'hello@digmarketing.com', '0277123456'),
]

customers = []
for name, email, phone in customers_data:
    customer, created = Customer.objects.get_or_create(
        business=business,
        email=email,
        defaults={
            'name': name,
            'phone': phone,
            'created_by': user
        }
    )
    customers.append(customer)
print(f"  ✅ Created {len(customers)} customers")

# Summary
print("\n"+"="*80)
print("✅ DATABASE POPULATION COMPLETE!")
print("="*80)
print(f"\n📊 Summary:")
print(f"  Users: {User.objects.count()}")
print(f"  Businesses: {Business.objects.count()}")
print(f"  Warehouses: {Warehouse.objects.count()}")
print(f"  Storefronts: {StoreFront.objects.count()}")
print(f"  Categories: {Category.objects.count()}")
print(f"  Products: {Product.objects.count()}")
print(f"  Stock Products: {StockProduct.objects.count()}")
print(f"  Storefront Inventory: {StoreFrontInventory.objects.count()}")
print(f"  Customers: {Customer.objects.count()}")

print(f"\n🔐 Login Credentials:")
print(f"  Email: mikedit009@gmail.com")
print(f"  Password: TestPass123!")

print(f"\n🚀 Ready to use!")
print("="*80)
