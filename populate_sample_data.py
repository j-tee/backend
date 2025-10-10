#!/usr/bin/env python
"""
Sample Data Population Script for Existing Business
Generates realistic business data from January to October 2025

This script uses your existing business and creates        print(f"{'✅ Created' if created else '✅ Found'} Warehouse: {self.warehouse.name}")
        
        # Get all storefronts for this business
        business_storefronts = BusinessStoreFront.objects.filter(
            business=self.business,
            is_active=True
        ).select_related('storefront')
        
        if not business_storefronts.exists():
            # Create a default storefront if none exists
            storefront = StoreFront.objects.create(
                business=self.business,
                name='Main Store',
                location='Accra Central, Ghana',
                manager=self.user,
                user=self.user
            )
            BusinessStoreFront.objects.create(
                business=self.business,
                storefront=storefront,
                is_active=True
            )
            self.storefronts = [storefront]
            print(f"✅ Created StoreFront: {storefront.name}")
        else:
            self.storefronts = [bs.storefront for bs in business_storefronts]
            print(f"\n✅ Found {len(self.storefronts)} StoreFronts:")
            for storefront in self.storefronts:
                print(f"   - {storefront.name} ({storefront.location})")rs
2. Products with categories
3. Stock intake across multiple months
4. Stock adjustments (damage, theft, etc.)
5. Customers (walk-in, retail, wholesale)
6. Sales transactions (cash, credit, card)
7. Payment records

Usage:
    python populate_sample_data.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal
from random import randint, choice, uniform, sample
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.utils import timezone
from django.db import transaction
from django.db.models import Sum

from accounts.models import User, Business, BusinessMembership
from inventory.models import (
    Category, Supplier, Warehouse, StoreFront, Product, Stock, StockProduct,
    StoreFrontInventory, BusinessWarehouse, BusinessStoreFront, TransferRequest,
    TransferRequestLineItem
)
from inventory.stock_adjustments import StockAdjustment
from sales.models import Customer, Sale, SaleItem, Payment

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
]

# Supplier information
SUPPLIERS = [
    {'name': 'TechWorld Supplies', 'contact': 'John Tech', 'phone': '+233244567890', 'email': 'contact@techworld.com'},
    {'name': 'Beverage Distributors Ltd', 'contact': 'Mary Drinks', 'phone': '+233244567891', 'email': 'sales@bevdist.com'},
    {'name': 'FoodMart Wholesale', 'contact': 'Peter Food', 'phone': '+233244567892', 'email': 'orders@foodmart.com'},
    {'name': 'HomeGoods Suppliers', 'contact': 'Sarah Home', 'phone': '+233244567893', 'email': 'info@homegoods.com'},
]

# Customer names
CUSTOMER_FIRST_NAMES = [
    'Kwame', 'Kofi', 'Kwasi', 'Yaw', 'Kojo', 'Ama', 'Akua', 'Adwoa', 'Afia', 'Esi',
    'James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda'
]

CUSTOMER_LAST_NAMES = [
    'Mensah', 'Osei', 'Boateng', 'Owusu', 'Appiah', 'Agyei', 'Asante', 'Gyasi',
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones'
]


class DataPopulator:
    def __init__(self):
        self.business = None
        self.user = None
        self.warehouse = None
        self.storefronts = []  # Changed to list to support multiple storefronts
        self.suppliers = []
        self.categories = {}
        self.products = []
        self.customers = []
        self.stocks_by_month = {}
        self.receipt_counter = 10000
        
    def random_datetime(self, start_date, end_date=None, business_hours=True):
        """Generate random datetime within range"""
        if end_date is None:
            end_date = start_date + timedelta(days=1)
            
        delta = end_date - start_date
        random_seconds = randint(0, int(delta.total_seconds()))
        dt = start_date + timedelta(seconds=random_seconds)
        
        if business_hours:
            hour = randint(8, 19)
            minute = randint(0, 59)
            dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    
    def select_business(self):
        """Let user select which business to populate"""
        print("\n" + "="*80)
        print("🏢 AVAILABLE BUSINESSES")
        print("="*80)
        
        businesses = list(Business.objects.all())
        if not businesses:
            print("❌ No businesses found. Please create a business first.")
            sys.exit(1)
        
        for idx, business in enumerate(businesses, 1):
            owner_membership = BusinessMembership.objects.filter(
                business=business, role=BusinessMembership.OWNER
            ).first()
            owner_name = owner_membership.user.name if owner_membership else "No Owner"
            member_count = BusinessMembership.objects.filter(business=business).count()
            
            print(f"\n{idx}. {business.name}")
            print(f"   Owner: {owner_name}")
            print(f"   Members: {member_count}")
        
        # Prefer DataLogique Systems if it exists
        datalogique = Business.objects.filter(name='DataLogique Systems').first()
        if datalogique:
            print(f"\n✅ Selected: {datalogique.name}")
            return datalogique
        
        # Otherwise use the first business
        selected_business = businesses[0]
        print(f"\n✅ Selected: {selected_business.name}")
        return selected_business
    
    def setup_base_data(self):
        """Setup business, user, warehouse, and storefront"""
        print("\n" + "="*80)
        print("🏢 SETTING UP BASE DATA")
        print("="*80)
        
        # Select business
        self.business = self.select_business()
        
        # Get business owner
        owner_membership = BusinessMembership.objects.filter(
            business=self.business, 
            role=BusinessMembership.OWNER
        ).first()
        
        if not owner_membership:
            print("❌ No owner found for the business.")
            sys.exit(1)
            
        self.user = owner_membership.user
        
        print(f"\n✅ Business: {self.business.name}")
        print(f"✅ Owner: {self.user.name} ({self.user.email})")
        
        # Show all business members
        all_members = BusinessMembership.objects.filter(business=self.business)
        print(f"✅ Total Members: {all_members.count()}")
        for membership in all_members:
            print(f"   - {membership.user.name} ({membership.role})")
        
        # Create or get warehouse
        # Check if business already has a warehouse
        business_warehouse = BusinessWarehouse.objects.filter(
            business=self.business,
            is_active=True
        ).select_related('warehouse').first()
        
        if business_warehouse:
            self.warehouse = business_warehouse.warehouse
            print(f"\n✅ Found Warehouse: {self.warehouse.name}")
        else:
            # Create new warehouse
            self.warehouse = Warehouse.objects.create(
                name='Main Warehouse',
                location='Accra, Ghana',
                manager=self.user
            )
            BusinessWarehouse.objects.create(
                business=self.business,
                warehouse=self.warehouse,
                is_active=True
            )
            print(f"\n✅ Created Warehouse: {self.warehouse.name}")
        
        # Get all storefronts for this business
        business_storefronts = BusinessStoreFront.objects.filter(
            business=self.business,
            is_active=True
        ).select_related('storefront')
        
        if not business_storefronts.exists():
            # Create a default storefront if none exists
            storefront = StoreFront.objects.create(
                name='Main Store',
                location='Accra Central, Ghana',
                manager=self.user,
                user=self.user
            )
            BusinessStoreFront.objects.create(
                business=self.business,
                storefront=storefront,
                is_active=True
            )
            self.storefronts = [storefront]
            print(f"\n✅ Created StoreFront: {storefront.name}")
        else:
            self.storefronts = [bs.storefront for bs in business_storefronts]
            print(f"\n✅ Found {len(self.storefronts)} StoreFronts:")
            for storefront in self.storefronts:
                print(f"   - {storefront.name} ({storefront.location})")
    
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
                    'address': f"{supplier_data['name']} Building, Accra"
                }
            )
            self.suppliers.append(supplier)
            print(f"  {'✅ Created' if created else '✅ Found'}: {supplier.name}")
    
    def setup_categories_and_products(self):
        """Create categories and products"""
        print("\n" + "="*80)
        print("📦 CREATING CATEGORIES AND PRODUCTS")
        print("="*80)
        
        # Create categories (global, not business-specific)
        category_names = set(template['category'] for template in PRODUCT_TEMPLATES)
        for cat_name in category_names:
            category, created = Category.objects.get_or_create(
                name=cat_name,
                defaults={'description': f'{cat_name} products'}
            )
            self.categories[cat_name] = category
            print(f"  {'✅ Created' if created else '✅ Found'} Category: {cat_name}")
        
        print("\n📦 Creating Products:")
        # Create products with business-specific SKUs
        existing_skus = set(Product.objects.filter(business=self.business).values_list('sku', flat=True))
        sku_counter = {}
        
        for template in PRODUCT_TEMPLATES:
            prefix = template['sku_prefix']
            if prefix not in sku_counter:
                sku_counter[prefix] = 1
            
            # Generate unique SKU
            while True:
                sku = f"{prefix}-{sku_counter[prefix]:04d}"
                if sku not in existing_skus:
                    break
                sku_counter[prefix] += 1
            
            sku_counter[prefix] += 1
            
            # Store pricing info
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
        
        # Create retail customers
        print("\n  Creating Retail Customers:")
        for i in range(15):
            first = choice(CUSTOMER_FIRST_NAMES)
            last = choice(CUSTOMER_LAST_NAMES)
            name = f"{first} {last}"
            phone = f"+233{randint(200000000, 599999999)}"
            
            customer, created = Customer.objects.get_or_create(
                business=self.business,
                phone=phone,
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
                print(f"    ✅ {name}")
        
        # Create wholesale customers
        print("\n  Creating Wholesale Customers:")
        for i in range(5):
            name = f"{choice(['Best', 'Quick', 'Super', 'Mega', 'Prime'])} {choice(['Shop', 'Store', 'Mart', 'Market'])} Ltd"
            phone = f"+233{randint(200000000, 599999999)}"
            
            customer, created = Customer.objects.get_or_create(
                business=self.business,
                phone=phone,
                defaults={
                    'name': name,
                    'email': f"orders@{name.lower().replace(' ', '')[:20]}.com",
                    'customer_type': 'WHOLESALE',
                    'credit_limit': Decimal(str(randint(5000, 20000))),
                    'credit_terms_days': choice([30, 45, 60]),
                    'created_by': self.user
                }
            )
            if created:
                self.customers.append(customer)
                print(f"    ✅ {name}")
    
    def generate_stock_for_month(self, year, month):
        """Generate stock intake for a specific month"""
        month_name = datetime(year, month, 1).strftime('%B %Y')
        print(f"\n  📅 {month_name}:")
        
        num_intakes = randint(2, 3)  # 2-3 stock intakes per month
        
        for intake_num in range(num_intakes):
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
            
            # Select random products
            intake_products = sample(self.products, min(randint(8, 12), len(self.products)))
            
            print(f"\n    🚚 Stock Intake #{intake_num + 1} on {intake_date.strftime('%Y-%m-%d')}:")
            
            for product_data in intake_products:
                product = product_data['product']
                template = product_data['template']
                
                # Match supplier to category
                category_name = product.category.name
                supplier = choice(self.suppliers)
                for sup in self.suppliers:
                    if category_name.lower() in sup.name.lower():
                        supplier = sup
                        break
                
                # Quantity based on category
                if category_name == 'Electronics':
                    quantity = randint(20, 50)
                elif category_name == 'Beverages':
                    quantity = randint(100, 300)
                elif category_name == 'Food':
                    quantity = randint(50, 200)
                else:
                    quantity = randint(30, 100)
                
                # Pricing
                unit_cost = template['_cost']
                retail_price = unit_cost * (Decimal('1') + template['_margin'])
                retail_price = Decimal(str(round(float(retail_price), 2)))
                wholesale_price = retail_price * Decimal('0.85')
                
                # Create Stock batch
                stock, created = Stock.objects.get_or_create(
                    arrival_date=intake_date.date(),
                    defaults={
                        'description': f'Stock intake for {month_name}'
                    }
                )
                
                # Create StockProduct entry
                stock_product = StockProduct.objects.create(
                    stock=stock,
                    warehouse=self.warehouse,
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
                
                print(f"      ✅ {product.name}: {quantity} units @ GH₵{unit_cost}")
    
    def create_and_fulfill_transfer_request(self, storefront, product, quantity, created_at):
        """
        Create and fulfill a transfer request to move stock from warehouse to storefront.
        This follows the correct data flow: Warehouse → Transfer Request → Fulfillment → Storefront
        """
        # Create transfer request
        transfer_request = TransferRequest.objects.create(
            business=self.business,
            storefront=storefront,
            requested_by=self.user,
            priority='MEDIUM',
            status='NEW',
            notes=f'Stock request for {product.name} - Sample Data',
            created_at=created_at
        )
        
        # Create line item
        TransferRequestLineItem.objects.create(
            transfer_request=transfer_request,
            product=product,
            requested_quantity=quantity
        )
        
        # Fulfill the request (this creates/updates StoreFrontInventory)
        transfer_request.apply_manual_inventory_fulfillment()
        transfer_request.status = 'FULFILLED'
        transfer_request.fulfilled_at = created_at
        transfer_request.fulfilled_by = self.user
        transfer_request.save(update_fields=['status', 'fulfilled_at', 'fulfilled_by', 'updated_at'])
        
        return transfer_request
    
    def generate_sales_for_month(self, year, month):
        """Generate sales for a specific month with proper stock flow"""
        month_name = datetime(2025, month, 1).strftime('%B %Y')
        
        # Get available stocks
        month_key_prefix = f"{year}-{month:02d}"
        available_stocks = []
        for key, stocks in self.stocks_by_month.items():
            if key.startswith(month_key_prefix):
                available_stocks.extend(stocks)
        
        if not available_stocks:
            print(f"\n  ⚠️  No stock available for sales in {month_name}")
            return
        
        print(f"\n  💰 Generating Sales for {month_name}:")
        
        # STEP 1: Create Transfer Requests to move stock to storefronts
        print(f"  📦 Creating Transfer Requests...")
        transfer_requests_created = self._create_transfer_requests_for_month(
            year, month, available_stocks
        )
        
        # Distribute sales across both storefronts
        num_sales = randint(20, 40)  # 20-40 sales per month
        
        for sale_num in range(num_sales):
            # Randomly select a storefront for this sale
            storefront = choice(self.storefronts)
            
            stock_data = choice(available_stocks)
            stock_product = stock_data['stock_product']
            intake_date = stock_data['intake_date']
            product = stock_data['product']
            
            # Check available quantity (original quantity minus sold quantity)
            # Get total sold from this stock_product
            sold_quantity = SaleItem.objects.filter(
                stock_product=stock_product
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            available_qty = int(stock_product.quantity - sold_quantity)
            
            if available_qty <= 0:
                continue
            
            # Sale date after stock intake
            if month == 10:
                month_end = datetime(year, month, 6, 23, 59)
            else:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                month_end = datetime(year, month, last_day, 23, 59)
            
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
                if randint(1, 100) <= 30:
                    payment_type = 'CREDIT'
                    is_credit = True
                else:
                    payment_type = choice(['CASH', 'CARD', 'MOMO'])
                    is_credit = False
            
            # Quantity
            max_qty = min(available_qty, 10 if sale_type == 'RETAIL' else 30)
            quantity = randint(1, max(1, int(max_qty)))
            
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
                storefront=storefront,  # Use the randomly selected storefront
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
            SaleItem.objects.create(
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
            
            # Note: DO NOT manually update stock_product.quantity
            # The system automatically tracks available quantity through stock movements
            # Modifying quantity after sales would violate stock integrity
            
            # Handle payment
            if not is_credit:
                Payment.objects.create(
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
                sale.status = 'PENDING'
                sale.save()
                customer.outstanding_balance += line_total
                customer.save()
            
            if (sale_num + 1) % 10 == 0:
                print(f"    💰 Created {sale_num + 1}/{num_sales} sales...")
        
        print(f"    ✅ Completed {num_sales} sales for {month_name}")
        
        # Print sales distribution by storefront
        sales_by_storefront = {}
        for storefront in self.storefronts:
            count = Sale.objects.filter(
                business=self.business,
                storefront=storefront,
                created_at__year=year,
                created_at__month=month
            ).count()
            sales_by_storefront[storefront.name] = count
        
        print(f"    📊 Sales Distribution:")
        for sf_name, count in sales_by_storefront.items():
            print(f"       {sf_name}: {count} sales")
    
    def populate_monthly_data(self):
        """Generate data for each month"""
        print("\n" + "="*80)
        print("📊 GENERATING MONTHLY DATA (January - October 2025)")
        print("="*80)
        
        for month in range(1, 11):
            month_name = datetime(2025, month, 1).strftime('%B %Y')
            print(f"\n{'='*80}")
            print(f"📅 PROCESSING {month_name.upper()}")
            print(f"{'='*80}")
            
            print(f"\n🚚 Stock Intake:")
            self.generate_stock_for_month(2025, month)
            
            print(f"\n💰 Sales Transactions:")
            self.generate_sales_for_month(2025, month)
    
    def print_summary(self):
        """Print summary"""
        print("\n" + "="*80)
        print("📊 DATA GENERATION SUMMARY")
        print("="*80)
        
        total_products = Product.objects.filter(business=self.business).count()
        total_stocks = Stock.objects.all().count()  # Stock doesn't have business field
        total_stock_products = StockProduct.objects.filter(warehouse=self.warehouse).count()
        total_customers = Customer.objects.filter(business=self.business).count()
        total_sales = Sale.objects.filter(business=self.business).count()
        total_payments = Payment.objects.filter(customer__business=self.business).count()
        
        print(f"\n✅ Products Created: {total_products}")
        print(f"✅ Stock Batches: {total_stocks}")
        print(f"✅ Stock Product Entries: {total_stock_products}")
        print(f"✅ Customers: {total_customers}")
        print(f"✅ Sales: {total_sales}")
        print(f"✅ Payments: {total_payments}")
        
        completed_sales = Sale.objects.filter(business=self.business, status='COMPLETED').count()
        pending_sales = Sale.objects.filter(business=self.business, status='PENDING').count()
        
        print(f"\n📊 Sales Status:")
        print(f"  ✅ Completed: {completed_sales}")
        print(f"  ⏳ Pending: {pending_sales}")
        
        # Sales by storefront
        print(f"\n🏪 Sales by Storefront:")
        for storefront in self.storefronts:
            storefront_sales = Sale.objects.filter(
                business=self.business,
                storefront=storefront
            ).count()
            storefront_revenue = Sale.objects.filter(
                business=self.business,
                storefront=storefront,
                status='COMPLETED'
            ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
            print(f"  📍 {storefront.name}:")
            print(f"     Sales: {storefront_sales}")
            print(f"     Revenue: GH₵{storefront_revenue:,.2f}")
        
        total_revenue = Sale.objects.filter(
            business=self.business,
            status='COMPLETED'
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        
        outstanding = Customer.objects.filter(
            business=self.business
        ).aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0')
        
        print(f"\n💵 Financial Summary:")
        print(f"  💰 Total Revenue: GH₵{total_revenue:,.2f}")
        print(f"  📊 Outstanding Credit: GH₵{outstanding:,.2f}")
        
        print("\n" + "="*80)
        print("✅ DATA POPULATION COMPLETE!")
        print("="*80 + "\n")


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("🚀 SAMPLE DATA POPULATION SCRIPT")
    print("="*80)
    print(f"📅 Period: January 2025 - October 2025")
    
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
