#!/usr/bin/env python
"""
Comprehensive Data Population Script for POS System
Generates realistic business data from January to October 2025

This script:
1. Creates suppliers
2. Generates monthly stock intake with realistic timing
3. Creates stock adjustments (damage, theft, spoilage) AFTER stock intake
4. Generates customer database
5. Creates sales (walk-in and credit customers) AFTER stock availability
6. Records payments including late payments for credit sales
7. Maintains date consistency throughout all operations

Usage:
    python populate_data.py
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

# Note: In this system:
# - Product: Basic product info (name, SKU, category, etc.)
# - Stock: Batch of stock intake for warehouse
# - StockProduct: Links product to stock with pricing, quantity, supplier

User = get_user_model()

# Configuration
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 10, 6)  # Current date

# Product templates with realistic pricing
PRODUCT_TEMPLATES = [
    # Electronics
    {'name': 'Samsung Galaxy A14', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 150, 'cost_max': 200, 'margin': 0.25},
    {'name': 'iPhone 13', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 600, 'cost_max': 800, 'margin': 0.20},
    {'name': 'HP Laptop 15"', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 400, 'cost_max': 600, 'margin': 0.22},
    {'name': 'Sony Headphones', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 50, 'cost_max': 100, 'margin': 0.30},
    {'name': 'Samsung TV 43"', 'category': 'Electronics', 'sku_prefix': 'ELEC', 'cost_min': 300, 'cost_max': 450, 'margin': 0.20},
    
    # Beverages
    {'name': 'Coca Cola 500ml', 'category': 'Beverages', 'sku_prefix': 'BEV', 'cost_min': 0.5, 'cost_max': 0.8, 'margin': 0.40},
    {'name': 'Sprite 1L', 'category': 'Beverages', 'sku_prefix': 'BEV', 'cost_min': 0.8, 'cost_max': 1.2, 'margin': 0.40},
    {'name': 'Malta Guinness', 'category': 'Beverages', 'sku_prefix': 'BEV', 'cost_min': 1.0, 'cost_max': 1.5, 'margin': 0.35},
    {'name': 'Bottled Water 750ml', 'category': 'Beverages', 'sku_prefix': 'BEV', 'cost_min': 0.3, 'cost_max': 0.5, 'margin': 0.50},
    {'name': 'Energy Drink 250ml', 'category': 'Beverages', 'sku_prefix': 'BEV', 'cost_min': 1.5, 'cost_max': 2.0, 'margin': 0.35},
    
    # Food Items
    {'name': 'Rice 5kg Bag', 'category': 'Food', 'sku_prefix': 'FOOD', 'cost_min': 8, 'cost_max': 12, 'margin': 0.25},
    {'name': 'Cooking Oil 2L', 'category': 'Food', 'sku_prefix': 'FOOD', 'cost_min': 6, 'cost_max': 9, 'margin': 0.22},
    {'name': 'Sugar 1kg', 'category': 'Food', 'sku_prefix': 'FOOD', 'cost_min': 1.5, 'cost_max': 2.5, 'margin': 0.30},
    {'name': 'Pasta 500g', 'category': 'Food', 'sku_prefix': 'FOOD', 'cost_min': 1.2, 'cost_max': 2.0, 'margin': 0.35},
    {'name': 'Canned Tomatoes', 'category': 'Food', 'sku_prefix': 'FOOD', 'cost_min': 0.8, 'cost_max': 1.5, 'margin': 0.40},
    
    # Household Items
    {'name': 'Detergent Powder 1kg', 'category': 'Household', 'sku_prefix': 'HOUSE', 'cost_min': 3, 'cost_max': 5, 'margin': 0.30},
    {'name': 'Toilet Paper 12-pack', 'category': 'Household', 'sku_prefix': 'HOUSE', 'cost_min': 4, 'cost_max': 6, 'margin': 0.25},
    {'name': 'Dish Soap 500ml', 'category': 'Household', 'sku_prefix': 'HOUSE', 'cost_min': 1.5, 'cost_max': 2.5, 'margin': 0.35},
    {'name': 'Broom', 'category': 'Household', 'sku_prefix': 'HOUSE', 'cost_min': 3, 'cost_max': 5, 'margin': 0.40},
    {'name': 'Bucket 10L', 'category': 'Household', 'sku_prefix': 'HOUSE', 'cost_min': 2, 'cost_max': 4, 'margin': 0.45},
    
    # Clothing
    {'name': 'T-Shirt Cotton', 'category': 'Clothing', 'sku_prefix': 'CLOTH', 'cost_min': 5, 'cost_max': 10, 'margin': 0.50},
    {'name': 'Jeans Denim', 'category': 'Clothing', 'sku_prefix': 'CLOTH', 'cost_min': 15, 'cost_max': 25, 'margin': 0.45},
    {'name': 'Sneakers', 'category': 'Clothing', 'sku_prefix': 'CLOTH', 'cost_min': 20, 'cost_max': 40, 'margin': 0.40},
    {'name': 'Polo Shirt', 'category': 'Clothing', 'sku_prefix': 'CLOTH', 'cost_min': 8, 'cost_max': 15, 'margin': 0.45},
    {'name': 'Socks 3-pack', 'category': 'Clothing', 'sku_prefix': 'CLOTH', 'cost_min': 3, 'cost_max': 6, 'margin': 0.50},
]

# Supplier information
SUPPLIERS = [
    {'name': 'TechWorld Supplies', 'contact': 'John Tech', 'phone': '+1234567890', 'email': 'contact@techworld.com'},
    {'name': 'Beverage Distributors Ltd', 'contact': 'Mary Drinks', 'phone': '+1234567891', 'email': 'sales@bevdist.com'},
    {'name': 'FoodMart Wholesale', 'contact': 'Peter Food', 'phone': '+1234567892', 'email': 'orders@foodmart.com'},
    {'name': 'HomeGoods Suppliers', 'contact': 'Sarah Home', 'phone': '+1234567893', 'email': 'info@homegoods.com'},
    {'name': 'Fashion Wholesale Inc', 'contact': 'David Style', 'phone': '+1234567894', 'email': 'sales@fashionwholesale.com'},
]

# Customer names for variety
CUSTOMER_FIRST_NAMES = [
    'James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda',
    'William', 'Elizabeth', 'David', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica',
    'Thomas', 'Sarah', 'Charles', 'Karen', 'Christopher', 'Nancy', 'Daniel', 'Lisa'
]

CUSTOMER_LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
    'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas',
    'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Thompson', 'White', 'Harris'
]


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
        self.stocks_by_month = {}  # Track stock intake dates for consistency
        self.receipt_counter = 10000  # Counter for unique receipt numbers
        
    def random_datetime(self, start_date, end_date=None, business_hours=True):
        """Generate random datetime within range"""
        if end_date is None:
            end_date = start_date + timedelta(days=1)
            
        delta = end_date - start_date
        random_seconds = randint(0, int(delta.total_seconds()))
        dt = start_date + timedelta(seconds=random_seconds)
        
        if business_hours:
            # Set to business hours (8 AM - 8 PM)
            hour = randint(8, 19)
            minute = randint(0, 59)
            dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    
    def setup_base_data(self):
        """Create business, user, warehouse, and storefront"""
        print("\n" + "="*80)
        print("🏢 SETTING UP BASE DATA")
        print("="*80)
        
        # Get or create business and user
        self.business = Business.objects.first()
        if not self.business:
            print("❌ No business found. Please create a business first.")
            sys.exit(1)
            
        self.user = User.objects.filter(business_memberships__business=self.business).first()
        if not self.user:
            print("❌ No user found. Please create a user first.")
            sys.exit(1)
        
        print(f"✅ Business: {self.business.name}")
        print(f"✅ User: {self.user.name}")
        
        # Create or get warehouse
        self.warehouse, created = Warehouse.objects.get_or_create(
            name='Main Warehouse',
            defaults={
                'location': '123 Warehouse District, Business City',
                'manager': self.user
            }
        )
        print(f"{'✅ Created' if created else '✅ Found'} Warehouse: {self.warehouse.name}")
        
        # Create or get storefront
        self.storefront, created = StoreFront.objects.get_or_create(
            name='Main Store',
            user=self.user,
            defaults={
                'location': '456 Main Street, Business City',
                'manager': self.user
            }
        )
        print(f"{'✅ Created' if created else '✅ Found'} StoreFront: {self.storefront.name}")
    
    def setup_suppliers(self):
        """Create supplier records"""
        print("\n" + "="*80)
        print("🏭 CREATING SUPPLIERS")
        print("="*80)
        
        for supplier_data in SUPPLIERS:
            supplier, created = Supplier.objects.get_or_create(
                business=self.business,
                name=supplier_data['name'],
                defaults={
                    'contact_person': supplier_data['contact'],
                    'phone_number': supplier_data['phone'],
                    'email': supplier_data['email'],
                    'address': f"{supplier_data['name']} Building, Supplier District"
                }
            )
            self.suppliers.append(supplier)
            print(f"  {'✅ Created' if created else '✅ Found'}: {supplier.name}")
    
    def setup_categories_and_products(self):
        """Create categories and products"""
        print("\n" + "="*80)
        print("📦 CREATING CATEGORIES AND PRODUCTS")
        print("="*80)
        
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
        # Create products
        sku_counter = {}
        for template in PRODUCT_TEMPLATES:
            prefix = template['sku_prefix']
            if prefix not in sku_counter:
                sku_counter[prefix] = 1
            
            sku = f"{prefix}-{sku_counter[prefix]:04d}"
            sku_counter[prefix] += 1
            
            # Store pricing info for later use with stock
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
            
            # Store product with its template for pricing later
            self.products.append({'product': product, 'template': template})
            print(f"  {'✅ Created' if created else '✅ Found'}: {product.name} ({sku})")
    
    def create_customers(self):
        """Create customer database"""
        print("\n" + "="*80)
        print("👥 CREATING CUSTOMERS")
        print("="*80)
        
        # Create walk-in customer
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
        
        # Create retail customers (20)
        print("\n  Creating Retail Customers:")
        for i in range(20):
            first = choice(CUSTOMER_FIRST_NAMES)
            last = choice(CUSTOMER_LAST_NAMES)
            name = f"{first} {last}"
            
            customer, created = Customer.objects.get_or_create(
                business=self.business,
                phone=f"+1234{randint(100000, 999999)}",
                defaults={
                    'name': name,
                    'email': f"{first.lower()}.{last.lower()}@email.com",
                    'customer_type': 'RETAIL',
                    'credit_limit': Decimal(str(randint(100, 1000))),
                    'credit_terms_days': choice([7, 14, 30]),
                    'created_by': self.user
                }
            )
            if created:
                self.customers.append(customer)
                print(f"    ✅ {name} (Credit: ${customer.credit_limit})")
        
        # Create wholesale customers (10)
        print("\n  Creating Wholesale Customers:")
        for i in range(10):
            name = f"{choice(['Best', 'Quick', 'Super', 'Mega', 'Prime'])} {choice(['Shop', 'Store', 'Mart', 'Market', 'Traders'])} Ltd"
            
            customer, created = Customer.objects.get_or_create(
                business=self.business,
                phone=f"+1235{randint(100000, 999999)}",
                defaults={
                    'name': name,
                    'email': f"orders@{name.lower().replace(' ', '')}.com",
                    'customer_type': 'WHOLESALE',
                    'credit_limit': Decimal(str(randint(5000, 20000))),
                    'credit_terms_days': choice([30, 45, 60]),
                    'created_by': self.user
                }
            )
            if created:
                self.customers.append(customer)
                print(f"    ✅ {name} (Credit: ${customer.credit_limit})")
    
    def generate_stock_for_month(self, year, month):
        """Generate stock intake for a specific month"""
        month_name = datetime(year, month, 1).strftime('%B %Y')
        print(f"\n  📅 {month_name}:")
        
        # Determine number of stock intakes for the month (2-4 times)
        num_intakes = randint(2, 4)
        
        for intake_num in range(num_intakes):
            # Random day in the month (avoid last 2 days to allow for sales)
            if month == 10:  # October - only up to current date
                max_day = 6
            else:
                import calendar
                max_day = calendar.monthrange(year, month)[1] - 2
            
            intake_day = randint(1, max(1, max_day))
            intake_date = self.random_datetime(
                datetime(year, month, intake_day),
                business_hours=True
            )
            
            # Select random products for this intake (10-15 products)
            intake_products = sample(self.products, min(randint(10, 15), len(self.products)))
            
            print(f"\n    🚚 Stock Intake #{intake_num + 1} on {intake_date.strftime('%Y-%m-%d %H:%M')}:")
            
            for product_data in intake_products:
                product = product_data['product']
                template = product_data['template']
                
                # Determine supplier based on category
                category_name = product.category.name
                supplier = None
                for sup in self.suppliers:
                    if category_name in sup.name or sup.name.split()[0] in category_name:
                        supplier = sup
                        break
                if not supplier:
                    supplier = choice(self.suppliers)
                
                # Quantity based on product type
                if category_name == 'Electronics':
                    quantity = randint(20, 100)
                elif category_name == 'Beverages':
                    quantity = randint(100, 500)
                elif category_name == 'Food':
                    quantity = randint(50, 300)
                else:
                    quantity = randint(30, 200)
                
                # Pricing from template
                unit_cost = template['_cost']
                retail_price = unit_cost * (Decimal('1') + template['_margin'])
                retail_price = Decimal(str(round(float(retail_price), 2)))
                wholesale_price = retail_price * Decimal('0.85')  # 15% discount for wholesale
                
                # Create Stock batch
                stock, created = Stock.objects.get_or_create(
                    warehouse=self.warehouse,
                    arrival_date=intake_date.date(),
                    defaults={
                        'description': f'Stock intake for {month_name}'
                    }
                )
                
                # Create StockProduct entry
                stock_product = StockProduct.objects.create(
                    stock=stock,
                    product=product,
                    supplier=supplier,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    retail_price=retail_price,
                    wholesale_price=wholesale_price,
                    description=f'Batch {intake_num + 1} for {month_name}'
                )
                
                # Track for later use
                key = f"{year}-{month:02d}-{product.id}"
                if key not in self.stocks_by_month:
                    self.stocks_by_month[key] = []
                self.stocks_by_month[key].append({
                    'stock_product': stock_product,
                    'intake_date': intake_date,
                    'product': product,
                    'quantity': quantity,
                    'retail_price': retail_price,
                    'wholesale_price': wholesale_price
                })
                
                print(f"      ✅ {product.name}: {quantity} units @ ${unit_cost}/unit from {supplier.name}")
    
    def generate_adjustments_for_month(self, year, month):
        """Generate stock adjustments for a specific month"""
        month_name = datetime(year, month, 1).strftime('%B %Y')
        
        # Get stocks for this month
        month_key_prefix = f"{year}-{month:02d}"
        month_stocks = []
        for key, stocks in self.stocks_by_month.items():
            if key.startswith(month_key_prefix):
                month_stocks.extend(stocks)
        
        if not month_stocks:
            return
        
        print(f"\n  ⚠️  Generating Adjustments for {month_name}:")
        
        # Generate 3-7 adjustments for the month
        num_adjustments = randint(3, 7)
        
        for i in range(num_adjustments):
            stock_data = choice(month_stocks)
            stock_product = stock_data['stock_product']
            intake_date = stock_data['intake_date']
            product = stock_data['product']
            
            # Adjustment must be AFTER stock intake
            # Random date between intake and end of month
            if month == 10:
                month_end = datetime(year, month, 6, 23, 59)
            else:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                month_end = datetime(year, month, last_day, 23, 59)
            
            # Make month_end timezone aware
            month_end = timezone.make_aware(month_end) if timezone.is_naive(month_end) else month_end
            
            # Ensure adjustment is after intake
            earliest_adj_date = intake_date + timedelta(days=1)
            if earliest_adj_date > month_end:
                continue
            
            adj_date = self.random_datetime(earliest_adj_date, month_end, business_hours=True)
            
            # Select adjustment type
            adj_types = [
                ('DAMAGE', -1, 'Damage/Breakage'),
                ('THEFT', -1, 'Theft/Shrinkage'),
                ('SPOILAGE', -1, 'Spoilage'),
                ('LOSS', -1, 'Lost/Missing'),
                ('EXPIRED', -1, 'Expired Product'),
            ]
            
            adj_type, multiplier, display = choice(adj_types)
            
            # Quantity to adjust (1-5% of stock)
            max_adjust = max(1, int(stock_product.quantity * 0.05))
            adj_quantity = randint(1, max_adjust) * multiplier
            
            # Create adjustment
            adjustment = StockAdjustment.objects.create(
                business=self.business,
                stock_product=stock_product,
                adjustment_type=adj_type,
                quantity=adj_quantity,
                reason=f'{display} - {product.name}',
                unit_cost=stock_product.unit_cost,
                approved_by=self.user,
                status='PENDING',
                requires_approval=True,
                created_at=adj_date
            )
            
            # Auto-approve and complete (simulate manager action)
            adjustment.approve(self.user)
            adjustment.complete()
            adjustment.approved_at = adj_date
            adjustment.completed_at = adj_date
            adjustment.save()
            
            print(f"    ⚠️  {display}: {product.name} ({adj_quantity} units) on {adj_date.strftime('%Y-%m-%d')}")
    
    def generate_sales_for_month(self, year, month):
        """Generate sales for a specific month"""
        month_name = datetime(year, month, 1).strftime('%B %Y')
        
        # Get available stocks for this month
        month_key_prefix = f"{year}-{month:02d}"
        available_stocks = []
        for key, stocks in self.stocks_by_month.items():
            if key.startswith(month_key_prefix):
                available_stocks.extend(stocks)
        
        if not available_stocks:
            print(f"\n  ⚠️  No stock available for sales in {month_name}")
            return
        
        print(f"\n  💰 Generating Sales for {month_name}:")
        
        # Generate 30-60 sales for the month
        num_sales = randint(30, 60)
        
        for sale_num in range(num_sales):
            # Pick random stock
            stock_data = choice(available_stocks)
            stock_product = stock_data['stock_product']
            intake_date = stock_data['intake_date']
            product = stock_data['product']
            
            # Check if stock is available
            if stock_product.quantity <= 0:
                continue
            
            # Sale date must be AFTER stock intake
            if month == 10:
                month_end = datetime(year, month, 6, 23, 59)
            else:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                month_end = datetime(year, month, last_day, 23, 59)
            
            # Make month_end timezone aware
            month_end = timezone.make_aware(month_end) if timezone.is_naive(month_end) else month_end
            
            earliest_sale_date = intake_date + timedelta(hours=2)
            if earliest_sale_date > month_end:
                continue
            
            sale_date = self.random_datetime(earliest_sale_date, month_end, business_hours=True)
            
            # Select customer
            customer = choice(self.customers)
            
            # Determine sale type
            if customer.name == 'Walk-in Customer':
                sale_type = 'RETAIL'
                payment_type = choice(['CASH', 'CARD', 'MOMO'])
                is_credit = False
            else:
                sale_type = customer.customer_type
                if randint(1, 100) <= 30:  # 30% credit sales
                    payment_type = 'CREDIT'
                    is_credit = True
                else:
                    payment_type = choice(['CASH', 'CARD', 'MOMO'])
                    is_credit = False
            
            # Quantity to sell
            max_qty = min(stock_product.quantity, 10 if sale_type == 'RETAIL' else 50)
            quantity = randint(1, max(1, max_qty))
            
            # Calculate amounts - use appropriate price based on sale type
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
                user=self.user,
                customer=customer,
                receipt_number=f"REC-{year}{month:02d}-{self.receipt_counter}",
                type=sale_type,
                status='PENDING',
                subtotal=line_total,
                total_amount=line_total,
                payment_type=payment_type,
                created_at=sale_date
            )
            
            # Create sale item
            sale_item = SaleItem.objects.create(
                sale=sale,
                product=product,
                stock=stock_product.stock,
                stock_product=stock_product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=line_total,
                product_name=product.name,
                product_sku=product.sku
            )
            
            # Update stock
            stock_product.quantity -= quantity
            stock_product.save()
            
            # Handle payment
            if not is_credit:
                # Immediate payment
                payment = Payment.objects.create(
                    sale=sale,
                    customer=customer,
                    amount_paid=line_total,
                    payment_method=payment_type,
                    status='SUCCESSFUL',
                    processed_by=self.user,
                    payment_date=sale_date
                )
                sale.amount_paid = line_total
                sale.status = 'COMPLETED'
                sale.save()
            else:
                # Credit sale
                sale.status = 'PENDING'
                sale.save()
                
                # Update customer balance
                customer.outstanding_balance += line_total
                customer.save()
                
                # Maybe pay later (60% chance of late payment)
                if randint(1, 100) <= 60:
                    # Payment 3-45 days later
                    days_late = randint(3, min(45, customer.credit_terms_days + 15))
                    payment_date = sale_date + timedelta(days=days_late)
                    
                    # Only create payment if it's before current date
                    if payment_date <= timezone.now():
                        # Partial or full payment
                        if randint(1, 100) <= 70:  # 70% full payment
                            payment_amount = line_total
                        else:  # 30% partial payment
                            payment_amount = line_total * Decimal(str(uniform(0.3, 0.8)))
                        
                        payment = Payment.objects.create(
                            sale=sale,
                            customer=customer,
                            amount_paid=payment_amount,
                            payment_method=choice(['CASH', 'BANK_TRANSFER', 'MOMO']),
                            status='SUCCESSFUL',
                            processed_by=self.user,
                            payment_date=payment_date
                        )
                        
                        # Update sale
                        sale.amount_paid += payment_amount
                        if sale.amount_paid >= sale.total_amount:
                            sale.status = 'COMPLETED'
                        else:
                            sale.status = 'PARTIAL'
                        sale.save()
                        
                        # Update customer balance
                        customer.outstanding_balance -= payment_amount
                        customer.save()
            
            if sale_num % 10 == 0:
                print(f"    💰 Created {sale_num + 1}/{num_sales} sales...")
        
        print(f"    ✅ Completed {num_sales} sales for {month_name}")
    
    def populate_monthly_data(self):
        """Generate data for each month from January to October"""
        print("\n" + "="*80)
        print("📊 GENERATING MONTHLY DATA (January - October 2025)")
        print("="*80)
        
        for month in range(1, 11):  # January to October
            month_name = datetime(2025, month, 1).strftime('%B %Y')
            print(f"\n{'='*80}")
            print(f"📅 PROCESSING {month_name.upper()}")
            print(f"{'='*80}")
            
            # 1. Generate stock intake
            print(f"\n🚚 Stock Intake:")
            self.generate_stock_for_month(2025, month)
            
            # 2. Generate adjustments (after stock intake)
            print(f"\n⚠️  Stock Adjustments:")
            self.generate_adjustments_for_month(2025, month)
            
            # 3. Generate sales (after stock available)
            print(f"\n💰 Sales Transactions:")
            self.generate_sales_for_month(2025, month)
    
    def print_summary(self):
        """Print summary of generated data"""
        print("\n" + "="*80)
        print("📊 DATA GENERATION SUMMARY")
        print("="*80)
        
        total_products = Product.objects.filter(business=self.business).count()
        total_stocks = Stock.objects.filter(warehouse=self.warehouse).count()
        total_stock_products = StockProduct.objects.filter(stock__warehouse=self.warehouse).count()
        total_adjustments = StockAdjustment.objects.filter(business=self.business).count()
        total_customers = Customer.objects.filter(business=self.business).count()
        total_sales = Sale.objects.filter(business=self.business).count()
        total_payments = Payment.objects.filter(customer__business=self.business).count()
        
        print(f"\n✅ Products Created: {total_products}")
        print(f"✅ Stock Batches: {total_stocks}")
        print(f"✅ Stock Product Entries: {total_stock_products}")
        print(f"✅ Stock Adjustments: {total_adjustments}")
        print(f"✅ Customers: {total_customers}")
        print(f"✅ Sales: {total_sales}")
        print(f"✅ Payments: {total_payments}")
        
        # Sales summary
        completed_sales = Sale.objects.filter(business=self.business, status='COMPLETED').count()
        pending_sales = Sale.objects.filter(business=self.business, status='PENDING').count()
        partial_sales = Sale.objects.filter(business=self.business, status='PARTIAL').count()
        
        print(f"\n📊 Sales Status:")
        print(f"  ✅ Completed: {completed_sales}")
        print(f"  ⏳ Pending: {pending_sales}")
        print(f"  💰 Partial: {partial_sales}")
        
        # Revenue
        total_revenue = Sale.objects.filter(
            business=self.business,
            status__in=['COMPLETED', 'PARTIAL']
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        
        outstanding = Customer.objects.filter(
            business=self.business
        ).aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0')
        
        print(f"\n💵 Financial Summary:")
        print(f"  💰 Total Revenue Collected: ${total_revenue:,.2f}")
        print(f"  📊 Outstanding Credit: ${outstanding:,.2f}")
        
        print("\n" + "="*80)
        print("✅ DATA POPULATION COMPLETE!")
        print("="*80 + "\n")


def main():
    """Main execution function"""
    print("\n" + "="*80)
    print("🚀 STARTING DATA POPULATION SCRIPT")
    print("="*80)
    print(f"📅 Period: January 2025 - October 2025")
    print(f"🏢 Generating realistic business data...")
    
    populator = DataPopulator()
    
    try:
        with transaction.atomic():
            populator.setup_base_data()
            populator.setup_suppliers()
            populator.setup_categories_and_products()
            populator.create_customers()
            populator.populate_monthly_data()
            populator.print_summary()
            
    except Exception as e:
        print(f"\n❌ Error during data population: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
