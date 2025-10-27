#!/usr/bin/env python
"""
Simplified Data Population Script for DataLogique Systems Business
Generates realistic business data from January to October 2025

This script follows the exact same pattern as populate_data.py but creates
data specifically for the DataLogique Systems business.

Usage:
    python populate_datalogique_simple.py
"""

import os
import sys
import django
from datetime import datetime, timedelta, time
from decimal import Decimal
from random import randint, choice, uniform, sample
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum

from accounts.models import Business, BusinessMembership
from inventory.models import (
    Category, Supplier, Warehouse, StoreFront, Product, Stock, StockProduct
)
from inventory.stock_adjustments import StockAdjustment
from sales.models import Customer, Sale, SaleItem, Payment

User = get_user_model()

# Configuration
BUSINESS_NAME = "DataLogique Systems"
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 10, 6)

# Product templates (28+ items across 4 categories)
PRODUCT_TEMPLATES = [
    # Electronics
    {'name': 'Laptop HP ProBook 450', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 2500, 'cost_max': 3000, 'margin': 0.28},
    {'name': 'Desktop Dell OptiPlex', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 1800, 'cost_max': 2200, 'margin': 0.33},
    {'name': 'Monitor Samsung 24"', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 180, 'cost_max': 250, 'margin': 0.35},
    {'name': 'Keyboard Logitech Wireless', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 25, 'cost_max': 40, 'margin': 0.40},
    {'name': 'Mouse Logitech MX Master', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 45, 'cost_max': 65, 'margin': 0.38},
    {'name': 'Printer HP LaserJet', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 350, 'cost_max': 450, 'margin': 0.30},
    {'name': 'External HDD 2TB Seagate', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 85, 'cost_max': 110, 'margin': 0.35},
    {'name': 'USB Flash Drive 64GB', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 12, 'cost_max': 18, 'margin': 0.45},
    
    # Office Supplies
    {'name': 'A4 Paper Ream 80gsm', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 8.5, 'cost_max': 12, 'margin': 0.41},
    {'name': 'Stapler Heavy Duty', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 6, 'cost_max': 10, 'margin': 0.50},
    {'name': 'Pen Box (50pcs)', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 15, 'cost_max': 22, 'margin': 0.45},
    {'name': 'Notebook A5 Ruled', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 2.5, 'cost_max': 4.5, 'margin': 0.60},
    {'name': 'File Folder Box (25pcs)', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 18, 'cost_max': 25, 'margin': 0.40},
    {'name': 'Sticky Notes Pack', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 3, 'cost_max': 6, 'margin': 0.67},
    {'name': 'Calculator Scientific', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 12, 'cost_max': 18, 'margin': 0.42},
    {'name': 'Desk Organizer Set', 'category': 'Office Supplies', 'sku_prefix': 'OFF', 'cost_min': 8, 'cost_max': 15, 'margin': 0.47},
    
    # Networking Equipment
    {'name': 'Router TP-Link AC1200', 'category': 'Networking', 'sku_prefix': 'NET', 'cost_min': 65, 'cost_max': 90, 'margin': 0.46},
    {'name': 'Switch Netgear 8-Port', 'category': 'Networking', 'sku_prefix': 'NET', 'cost_min': 35, 'cost_max': 50, 'margin': 0.43},
    {'name': 'Ethernet Cable Cat6 50m', 'category': 'Networking', 'sku_prefix': 'NET', 'cost_min': 18, 'cost_max': 28, 'margin': 0.43},
    {'name': 'Wifi Adapter USB', 'category': 'Networking', 'sku_prefix': 'NET', 'cost_min': 15, 'cost_max': 22, 'margin': 0.45},
    {'name': 'Patch Panel 24-Port', 'category': 'Networking', 'sku_prefix': 'NET', 'cost_min': 45, 'cost_max': 65, 'margin': 0.38},
    {'name': 'Network Cable Tester', 'category': 'Networking', 'sku_prefix': 'NET', 'cost_min': 25, 'cost_max': 38, 'margin': 0.52},
    
    # Software & Licenses
    {'name': 'Antivirus License 1-Year', 'category': 'Software', 'sku_prefix': 'SOFT', 'cost_min': 45, 'cost_max': 65, 'margin': 0.67},
    {'name': 'MS Office Home & Business', 'category': 'Software', 'sku_prefix': 'SOFT', 'cost_min': 180, 'cost_max': 220, 'margin': 0.36},
    {'name': 'Windows 10 Pro License', 'category': 'Software', 'sku_prefix': 'SOFT', 'cost_min': 120, 'cost_max': 160, 'margin': 0.38},
    {'name': 'Adobe Acrobat Pro DC', 'category': 'Software', 'sku_prefix': 'SOFT', 'cost_min': 140, 'cost_max': 180, 'margin': 0.39},
]

# Suppliers
SUPPLIERS = [
    {'name': 'TechHub Distributors', 'contact': 'John Mensah', 'phone': '+233244567890', 'email': 'sales@techhub.com.gh'},
    {'name': 'Office Pro Ghana', 'contact': 'Grace Owusu', 'phone': '+233244567891', 'email': 'orders@officepro.com.gh'},
    {'name': 'NetGear Supplies Ltd', 'contact': 'Samuel Boateng', 'phone': '+233244567892', 'email': 'info@netgear.com.gh'},
    {'name': 'Software Solutions Africa', 'contact': 'Mary Adjei', 'phone': '+233244567893', 'email': 'licensing@softafrica.com'},
]

# Customer names
CUSTOMER_FIRST_NAMES = ['Kwame', 'Ama', 'Kofi', 'Akua', 'Yaw', 'Abena', 'Kwesi', 'Efua', 'Kojo', 'Esi']
CUSTOMER_LAST_NAMES = ['Mensah', 'Owusu', 'Boateng', 'Adjei', 'Asante', 'Osei', 'Darko', 'Amoah', 'Opoku', 'Frimpong']

class DataPopulator:
    def __init__(self):
        self.business = None
        self.user = None
        self.warehouse = None
        self.storefront = None
        self.suppliers = []
        self.categories = {}
        self.products = []
        self.customers = []
        self.stocks_by_month = {}
        self.receipt_counter = 1000
        
    def random_datetime(self, start, end=None, business_hours=False):
        """Generate random datetime within range"""
        if end is None:
            end = start + timedelta(days=1)
        
        delta = end - start
        random_second = randint(0, int(delta.total_seconds()))
        dt = start + timedelta(seconds=random_second)
        
        if business_hours:
            # Set to business hours 9 AM - 6 PM
            dt = dt.replace(hour=randint(9, 18), minute=randint(0, 59))
        
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    
    def run(self):
        """Main execution"""
        print("=" * 80)
        print("🚀 DATA POPULATION FOR DATALOGIQUE SYSTEMS")
        print("=" * 80)
        
        with transaction.atomic():
            self.setup_business()
            self.setup_warehouse_and_storefront()
            self.setup_suppliers()
            self.setup_categories_and_products()
            self.create_customers()
            
            # Generate data month by month from January to October
            for month in range(1, 11):  # January to October
                month_name = datetime(2025, month, 1).strftime('%B %Y')
                print(f"\n{'='*80}")
                print(f"📅 PROCESSING: {month_name}")
                print(f"{'='*80}")
                
                self.generate_stock_for_month(2025, month)
                self.generate_adjustments_for_month(2025, month)
                self.generate_sales_for_month(2025, month)
        
        print("\n" + "="*80)
        print("✅ DATA POPULATION COMPLETED SUCCESSFULLY!")
        print("="*80)
        self.print_summary()
    
    def setup_business(self):
        """Get or create DataLogique Systems business"""
        print("\n🏢 Setting up Business:")
        
        # Get DataLogique Systems business
        self.business = Business.objects.filter(name=BUSINESS_NAME).first()
        
        if not self.business:
            print(f"  ❌ Business '{BUSINESS_NAME}' not found!")
            sys.exit(1)
        
        print(f"  ✅ Found Business: {self.business.name}")
        
        # Get owner user for this business
        membership = BusinessMembership.objects.filter(
            business=self.business,
            role='OWNER'
        ).first()
        
        if not membership:
            # Try STAFF as fallback
            membership = BusinessMembership.objects.filter(
                business=self.business
            ).first()
        
        if not membership:
            print(f"  ❌ No users found for {BUSINESS_NAME}")
            sys.exit(1)
        
        self.user = membership.user
        print(f"  ✅ Using user: {self.user.email}")
    
    def setup_warehouse_and_storefront(self):
        """Get or create warehouse and storefront"""
        print("\n📦 Setting up Warehouse and Storefront:")
        
        # Get warehouse managed by this user or create one
        self.warehouse = Warehouse.objects.filter(manager=self.user).first()
        if not self.warehouse:
            self.warehouse, created = Warehouse.objects.get_or_create(
                name=f'{BUSINESS_NAME} Warehouse',
                defaults={
                    'location': 'Accra, Ghana',
                    'capacity': 10000,
                    'manager': self.user
                }
            )
            print(f"  {'✅ Created' if created else '✅ Found'}: {self.warehouse.name}")
        else:
            print(f"  ✅ Found: {self.warehouse.name}")
        
        # Get storefront managed by this user or create one
        self.storefront = StoreFront.objects.filter(manager=self.user).first()
        if not self.storefront:
            self.storefront, created = StoreFront.objects.get_or_create(
                name=f'{BUSINESS_NAME} Store',
                defaults={
                    'location': 'Accra Central',
                    'warehouse': self.warehouse,
                    'manager': self.user
                }
            )
            print(f"  {'✅ Created' if created else '✅ Found'}: {self.storefront.name}")
        else:
            print(f"  ✅ Found: {self.storefront.name}")
    
    def setup_suppliers(self):
        """Create suppliers"""
        print("\n🚚 Creating Suppliers:")
        
        for supplier_data in SUPPLIERS:
            supplier, created = Supplier.objects.get_or_create(
                business=self.business,
                name=supplier_data['name'],
                defaults={
                    'contact_person': supplier_data['contact'],
                    'phone_number': supplier_data['phone'],
                    'email': supplier_data['email'],
                    'address': f"{supplier_data['name']} Building, Accra"
                }
            )
            self.suppliers.append(supplier)
            print(f"  {'✅ Created' if created else '✅ Found'}: {supplier.name}")
    
    def setup_categories_and_products(self):
        """Create categories and products"""
        print("\n📦 Creating Categories and Products:")
        
        # Create categories
        category_names = set(template['category'] for template in PRODUCT_TEMPLATES)
        for cat_name in category_names:
            category, created = Category.objects.get_or_create(
                name=cat_name,
                defaults={'description': f'{cat_name} products'}
            )
            self.categories[cat_name] = category
            print(f"  {'✅ Created' if created else '✅ Found'} Category: {cat_name}")
        
        print("\n📦 Creating Products:")
        sku_counter = {}
        for template in PRODUCT_TEMPLATES:
            prefix = template['sku_prefix']
            if prefix not in sku_counter:
                sku_counter[prefix] = 1
            
            sku = f"{prefix}-DL-{sku_counter[prefix]:04d}"  # DL for DataLogique
            sku_counter[prefix] += 1
            
            # Calculate pricing
            template['_cost'] = Decimal(str(round(uniform(template['cost_min'], template['cost_max']), 2)))
            template['_margin'] = Decimal(str(template['margin']))
            
            product, created = Product.objects.get_or_create(
                business=self.business,
                sku=sku,
                defaults={
                    'name': template['name'],
                    'description': f"Quality {template['name']}",
                    'category': self.categories[template['category']],
                    'unit': 'pcs',
                    'is_active': True
                }
            )
            
            self.products.append({'product': product, 'template': template})
            print(f"  {'✅ Created' if created else '✅ Found'}: {product.name} ({sku})")
    
    def create_customers(self):
        """Create customer database"""
        print("\n👥 Creating Customers:")
        
        # Walk-in customer
        walkin, created = Customer.objects.get_or_create(
            business=self.business,
            name='Walk-in Customer',
            defaults={
                'customer_type': 'RETAIL',
                'credit_limit': Decimal('0'),
                'created_by': self.user
            }
        )
        self.customers.append(walkin)
        print(f"  {'✅ Created' if created else '✅ Found'}: Walk-in Customer")
        
        # Business customers (5)
        print("\n  Creating Business Customers:")
        business_names = [
            'AccraNet Solutions',
            'Ghana Office Supplies Ltd',
            'TechPro Ghana',
            'Corporate IT Services',
            'Digital Hub Africa'
        ]
        
        for name in business_names:
            customer, created = Customer.objects.get_or_create(
                business=self.business,
                name=name,
                defaults={
                    'phone': f"+233{randint(200000000, 299999999)}",
                    'email': f"orders@{name.lower().replace(' ', '')}.com",
                    'customer_type': 'WHOLESALE',
                    'credit_limit': Decimal(str(randint(10000, 50000))),
                    'credit_terms_days': choice([30, 45, 60]),
                    'created_by': self.user
                }
            )
            if created:
                self.customers.append(customer)
                print(f"    ✅ {name} (Credit: GH¢{customer.credit_limit})")
    
    def generate_stock_for_month(self, year, month):
        """Generate stock intake for a specific month"""
        month_name = datetime(year, month, 1).strftime('%B %Y')
        print(f"\n  📅 {month_name}:")
        
        # 2-4 stock intakes per month
        num_intakes = randint(2, 4)
        
        for intake_num in range(num_intakes):
            # Random day in the month
            if month == 10:
                max_day = 6
            else:
                import calendar
                max_day = calendar.monthrange(year, month)[1] - 2
            
            intake_day = randint(1, max(1, max_day))
            intake_date = self.random_datetime(
                datetime(year, month, intake_day),
                business_hours=True
            )
            
            # Select 8-15 random products
            intake_products = sample(self.products, min(randint(8, 15), len(self.products)))
            
            print(f"\n    🚚 Stock Intake #{intake_num + 1} on {intake_date.strftime('%Y-%m-%d %H:%M')}:")
            
            for product_data in intake_products:
                product = product_data['product']
                template = product_data['template']
                
                # Select supplier
                supplier = choice(self.suppliers)
                
                # Quantity based on category
                category_name = product.category.name
                if category_name == 'Electronics':
                    quantity = randint(10, 50)
                elif category_name == 'Software':
                    quantity = randint(15, 40)
                else:
                    quantity = randint(30, 100)
                
                # Pricing
                unit_cost = template['_cost']
                retail_price = unit_cost * (Decimal('1') + template['_margin'])
                retail_price = Decimal(str(round(float(retail_price), 2)))
                wholesale_price = retail_price * Decimal('0.88')
                
                # Create Stock batch
                stock, _ = Stock.objects.get_or_create(
                    warehouse=self.warehouse,
                    arrival_date=intake_date.date(),
                    defaults={'description': f'Stock intake for {month_name}'}
                )
                
                # Create StockProduct
                stock_product, created = StockProduct.objects.get_or_create(
                    stock=stock,
                    product=product,
                    defaults={
                        'quantity': quantity,
                        'unit_cost': unit_cost,
                        'retail_price': retail_price,
                        'wholesale_price': wholesale_price,
                        'supplier': supplier
                    }
                )
                
                if not created:
                    stock_product.quantity += quantity
                    stock_product.save()
                
                # Store for sales generation
                month_key = f"{year}-{month:02d}-{intake_day:02d}"
                if month_key not in self.stocks_by_month:
                    self.stocks_by_month[month_key] = []
                
                self.stocks_by_month[month_key].append({
                    'stock_product': stock_product,
                    'product': product,
                    'intake_date': intake_date,
                    'retail_price': retail_price,
                    'wholesale_price': wholesale_price
                })
                
                print(f"      ✅ {product.name}: {quantity} units @ GH¢{unit_cost}/unit")
    
    def generate_adjustments_for_month(self, year, month):
        """Generate stock adjustments for a month"""
        month_key_prefix = f"{year}-{month:02d}"
        available_stocks = []
        for key, stocks in self.stocks_by_month.items():
            if key.startswith(month_key_prefix):
                available_stocks.extend(stocks)
        
        if not available_stocks:
            return
        
        # 2-5 adjustments per month
        num_adjustments = randint(2, 5)
        
        print(f"\n  ⚠️  Generating Adjustments:")
        for _ in range(num_adjustments):
            stock_data = choice(available_stocks)
            stock_product = stock_data['stock_product']
            intake_date = stock_data['intake_date']
            product = stock_data['product']
            
            if stock_product.quantity <= 0:
                continue
            
            # Adjustment date after stock receipt
            if month == 10:
                month_end = datetime(year, month, 6, 23, 59)
            else:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                month_end = datetime(year, month, last_day, 23, 59)
            
            month_end = timezone.make_aware(month_end) if timezone.is_naive(month_end) else month_end
            
            earliest_adj = intake_date + timedelta(days=1)
            if earliest_adj > month_end:
                continue
            
            adj_date = self.random_datetime(earliest_adj, month_end, business_hours=True)
            
            # Random adjustment type
            adj_type = choice(['DAMAGE', 'SPOILAGE', 'SHRINKAGE'])
            adj_quantity = randint(1, min(int(stock_product.quantity * 0.1), 10))
            
            # Create adjustment
            adjustment = StockAdjustment.objects.create(
                business=self.business,
                stock_product=stock_product,
                adjustment_type=adj_type,
                quantity=adj_quantity,
                reason=f'{adj_type} - {product.name}',
                unit_cost=stock_product.unit_cost,
                approved_by=self.user,
                status='PENDING',
                requires_approval=True,
                created_at=adj_date
            )
            
            # Auto-approve and complete
            adjustment.approve(self.user)
            adjustment.complete()
            adjustment.approved_at = adj_date
            adjustment.completed_at = adj_date
            adjustment.save()
            
            print(f"    ⚠️  {adj_type}: {product.name} ({adj_quantity} units)")
    
    def generate_sales_for_month(self, year, month):
        """Generate sales for a specific month"""
        month_name = datetime(year, month, 1).strftime('%B %Y')
        
        # Get available stocks
        month_key_prefix = f"{year}-{month:02d}"
        available_stocks = []
        for key, stocks in self.stocks_by_month.items():
            if key.startswith(month_key_prefix):
                available_stocks.extend(stocks)
        
        if not available_stocks:
            print(f"\n  ⚠️  No stock available for sales in {month_name}")
            return
        
        print(f"\n  💰 Generating Sales:")
        
        # 15-30 sales per month
        num_sales = randint(15, 30)
        
        for _ in range(num_sales):
            stock_data = choice(available_stocks)
            stock_product = stock_data['stock_product']
            intake_date = stock_data['intake_date']
            product = stock_data['product']
            
            if stock_product.quantity <= 0:
                continue
            
            # Sale date after stock intake
            if month == 10:
                month_end = datetime(year, month, 6, 23, 59)
            else:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                month_end = datetime(year, month, last_day, 23, 59)
            
            month_end = timezone.make_aware(month_end) if timezone.is_naive(month_end) else month_end
            
            earliest_sale = intake_date + timedelta(hours=2)
            if earliest_sale > month_end:
                continue
            
            sale_date = self.random_datetime(earliest_sale, month_end, business_hours=True)
            
            # Select customer
            customer = choice(self.customers)
            
            # Determine sale type
            if customer.name == 'Walk-in Customer':
                sale_type = 'RETAIL'
                payment_type = choice(['CASH', 'MOBILE', 'CARD'])  # Sale uses MOBILE
                is_credit = False
            else:
                sale_type = customer.customer_type
                if randint(1, 100) <= 30:
                    payment_type = 'CREDIT'
                    is_credit = True
                else:
                    payment_type = choice(['CASH', 'MOBILE', 'CARD'])  # Sale uses MOBILE
                    is_credit = False
            
            # Quantity
            max_qty = min(int(stock_product.quantity), 10 if sale_type == 'RETAIL' else 30)
            quantity = randint(1, max(1, max_qty))
            
            # Price
            if sale_type == 'WHOLESALE':
                unit_price = stock_data.get('wholesale_price', stock_product.wholesale_price)
            else:
                unit_price = stock_data.get('retail_price', stock_product.retail_price)
            
            line_total = unit_price * quantity
            
            # Create sale
            self.receipt_counter += 1
            sale = Sale.objects.create(
                business=self.business,
                storefront=self.storefront,
                customer=customer,
                user=self.user,
                receipt_number=f"REC-{year}{month:02d}-{self.receipt_counter:05d}",
                type=sale_type,  # Changed from sale_type to type
                payment_type=payment_type,
                subtotal=line_total,
                total_amount=line_total,
                amount_paid=Decimal('0') if is_credit else line_total,
                amount_due=line_total if is_credit else Decimal('0'),
                status='PENDING' if is_credit else 'COMPLETED',
                completed_at=sale_date if not is_credit else None,
                created_at=sale_date
            )
            
            # Create sale item
            SaleItem.objects.create(
                sale=sale,
                stock_product=stock_product,
                stock=stock_product.stock,  # Add stock reference
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=line_total,  # Changed from line_total to total_price
                product_name=product.name,
                product_sku=product.sku
            )
            
            # Reduce stock
            stock_product.quantity -= quantity
            stock_product.save()
            
            # Create payment if not credit
            if not is_credit:
                # Convert payment type for Payment model (MOBILE -> MOMO)
                payment_method = 'MOMO' if payment_type == 'MOBILE' else payment_type
                Payment.objects.create(
                    sale=sale,
                    customer=customer,  # Add customer - required field
                    amount_paid=line_total,  # Changed from amount to amount_paid
                    payment_method=payment_method,
                    payment_date=sale_date,
                    created_at=sale_date
                )
            else:
                # 30% chance of late payment for credit sales
                if randint(1, 100) <= 30:
                    days_late = randint(5, 15)
                    payment_date = sale_date + timedelta(days=days_late)
                    
                    late_payment_type = choice(['CASH', 'MOMO', 'CARD'])
                    Payment.objects.create(
                        sale=sale,
                        customer=customer,  # Add customer - required field
                        amount_paid=line_total,  # Changed from amount to amount_paid
                        payment_method=late_payment_type,  # Payment model uses MOMO directly
                        payment_date=payment_date,
                        created_at=payment_date
                    )
                    
                    sale.amount_paid = line_total
                    sale.amount_due = Decimal('0')
                    sale.status = 'COMPLETED'
                    sale.completed_at = payment_date
                    sale.save()
    
    def print_summary(self):
        """Print summary of generated data"""
        total_sales = Sale.objects.filter(business=self.business).count()
        completed_sales = Sale.objects.filter(business=self.business, status='COMPLETED').count()
        pending_sales = Sale.objects.filter(business=self.business, status='PENDING').count()
        
        total_revenue = Sale.objects.filter(
            business=self.business,
            status='COMPLETED'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        print(f"\n📊 Summary:")
        print(f"  Total Sales: {total_sales}")
        print(f"  Completed Sales: {completed_sales}")
        print(f"  Pending Sales: {pending_sales}")
        print(f"  Total Revenue: GH¢{total_revenue:,.2f}")

if __name__ == '__main__':
    populator = DataPopulator()
    populator.run()
