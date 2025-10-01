from __future__ import annotations

import random
import string
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    Business,
    BusinessMembership,
    Role,
)
from inventory.models import (
    BusinessStoreFront,
    BusinessWarehouse,
    Category,
    Inventory,
    Product,
    Stock,
    StockAlert,
    StockProduct,
    StoreFront,
    StoreFrontEmployee,
    Supplier,
    Transfer,
    Warehouse,
    WarehouseEmployee,
)
from sales.models import (
    CreditTransaction,
    Customer,
    Payment,
    Sale,
    SaleItem,
)
from subscriptions.models import (
    Invoice,
    Subscription,
    SubscriptionPayment,
    SubscriptionPlan,
)


User = get_user_model()

BUSINESS_BLUEPRINTS = [
    {
        "business_name": "Aurora Retail Group",
        "owner_name": "Aurora Sloan",
        "email": "aurora.sloan@example.com",
        "tin": "TIN-AURORA-001",
        "address": "102 Market Street, Accra",
        "phones": ["+233201100001", "+233201100051"],
        "social": {"instagram": "@auroraretail", "facebook": "aurora-retail"},
        "website": "https://auroraretail.example.com",
    },
    {
        "business_name": "BlueWave Traders",
        "owner_name": "Kwesi Djan",
        "email": "kwesi.djan@example.com",
        "tin": "TIN-BLUEWAVE-002",
        "address": "55 Liberation Road, Kumasi",
        "phones": ["+233201100002"],
        "social": {"instagram": "@bluewavegh"},
        "website": "https://bluewavetraders.example.com",
    },
    {
        "business_name": "Summit Essentials",
        "owner_name": "Lydia Boateng",
        "email": "lydia.boateng@example.com",
        "tin": "TIN-SUMMIT-003",
        "address": "17 Ridge Avenue, Takoradi",
        "phones": ["+233201100003", "+233201100063"],
        "social": {"twitter": "@summitessentials"},
        "website": "https://summitessentials.example.com",
    },
    {
        "business_name": "Coastal Fresh Mart",
        "owner_name": "Daniel Owusu",
        "email": "daniel.owusu@example.com",
        "tin": "TIN-COAST-004",
        "address": "8 Beach Road, Cape Coast",
        "phones": ["+233201100004"],
        "social": {"instagram": "@coastalfresh"},
        "website": "https://coastalfresh.example.com",
    },
    {
        "business_name": "Northern Harvest Hub",
        "owner_name": "Amina Fuseini",
        "email": "amina.fuseini@example.com",
        "tin": "TIN-NORTH-005",
        "address": "24 Tamale High Street, Tamale",
        "phones": ["+233201100005", "+233201100075"],
        "social": {"facebook": "northernharvest"},
        "website": "https://northernharvest.example.com",
    },
]

CATEGORY_DATA = [
    ("Beverages", "Non-alcoholic and alcoholic drinks"),
    ("Groceries", "Daily household grocery items"),
    ("Personal Care", "Cosmetics and personal hygiene"),
    ("Household Supplies", "Cleaning and home essentials"),
    ("Dairy", "Milk-based chilled goods"),
    ("Snacks", "Ready-to-eat snack foods"),
]

PRODUCT_DATA = [
    {
        "name": "Sparkle Orange Juice",
        "sku": "SP-ORJ-500",
        "category": "Beverages",
        "unit": "bottle",
        "retail_price": Decimal("24.99"),
        "wholesale_price": Decimal("19.50"),
        "cost": Decimal("15.25"),
        "description": "500ml bottled orange juice with vitamin C boost.",
    },
    {
        "name": "Harvest Long Grain Rice",
        "sku": "HV-LGR-25KG",
        "category": "Groceries",
        "unit": "bag",
        "retail_price": Decimal("320.00"),
        "wholesale_price": Decimal("285.00"),
        "cost": Decimal("240.00"),
        "description": "25kg sack of premium long grain rice.",
    },
    {
        "name": "UltraClean Detergent",
        "sku": "UC-DET-2L",
        "category": "Personal Care",
        "unit": "bottle",
        "retail_price": Decimal("54.00"),
        "wholesale_price": Decimal("48.00"),
        "cost": Decimal("36.00"),
        "description": "2L liquid detergent with antibacterial agents.",
    },
    {
        "name": "PureSpring Mineral Water",
        "sku": "PS-MW-1.5L",
        "category": "Beverages",
        "unit": "bottle",
        "retail_price": Decimal("12.50"),
        "wholesale_price": Decimal("9.00"),
        "cost": Decimal("7.20"),
        "description": "1.5L bottled mineral water sourced from natural springs.",
    },
    {
        "name": "GlowCare Shea Butter",
        "sku": "GC-SH-200",
        "category": "Personal Care",
        "unit": "jar",
        "retail_price": Decimal("68.00"),
        "wholesale_price": Decimal("59.50"),
        "cost": Decimal("45.00"),
        "description": "200g organic shea butter for skin and hair.",
    },
    {
        "name": "SunBite Plantain Chips",
        "sku": "SB-PC-100",
        "category": "Snacks",
        "unit": "pack",
        "retail_price": Decimal("9.50"),
        "wholesale_price": Decimal("7.80"),
        "cost": Decimal("5.10"),
        "description": "100g lightly salted plantain chips.",
    },
    {
        "name": "CrystalSpark Energy Drink",
        "sku": "CS-EN-330",
        "category": "Beverages",
        "unit": "can",
        "retail_price": Decimal("15.00"),
        "wholesale_price": Decimal("12.75"),
        "cost": Decimal("9.60"),
        "description": "330ml canned energy drink with vitamin complex.",
    },
    {
        "name": "Sunrise Evaporated Milk",
        "sku": "SR-EVM-410",
        "category": "Dairy",
        "unit": "can",
        "retail_price": Decimal("11.00"),
        "wholesale_price": Decimal("9.25"),
        "cost": Decimal("7.10"),
        "description": "410g can of fortified evaporated milk.",
    },
    {
        "name": "HomeBright Multipurpose Cleaner",
        "sku": "HB-MPC-750",
        "category": "Household Supplies",
        "unit": "bottle",
        "retail_price": Decimal("39.99"),
        "wholesale_price": Decimal("34.00"),
        "cost": Decimal("26.40"),
        "description": "750ml citrus scented multipurpose cleaner.",
    },
    {
        "name": "ChocoBite Wafer",
        "sku": "CB-WAF-050",
        "category": "Snacks",
        "unit": "pack",
        "retail_price": Decimal("6.50"),
        "wholesale_price": Decimal("5.20"),
        "cost": Decimal("3.80"),
        "description": "50g chocolate coated wafer snack.",
    },
    {
        "name": "Tropical Delight Yogurt",
        "sku": "TD-YOG-250",
        "category": "Dairy",
        "unit": "cup",
        "retail_price": Decimal("14.50"),
        "wholesale_price": Decimal("12.00"),
        "cost": Decimal("8.90"),
        "description": "250ml tropical fruit yogurt smoothie.",
    },
    {
        "name": "EcoFresh Paper Towels",
        "sku": "EF-PT-006",
        "category": "Household Supplies",
        "unit": "pack",
        "retail_price": Decimal("28.00"),
        "wholesale_price": Decimal("23.50"),
        "cost": Decimal("17.20"),
        "description": "6-pack eco-friendly 2-ply paper towels.",
    },
]

WAREHOUSE_LOCATIONS = [
    "Industrial Area, Accra",
    "Adum, Kumasi",
    "Harbour Road, Takoradi",
    "Tema Industrial Estate",
    "East Legon Logistics Park",
]

STOREFRONT_LOCATIONS = [
    "Osu Oxford Street, Accra",
    "Mallam Junction, Accra",
    "Kejetia Market, Kumasi",
    "Cape Coast Castle Market",
    "Tamale Central Market",
    "Takoradi Market Circle",
    "Madina Zongo Junction",
    "Kasoa New Market",
]

CUSTOMER_TEMPLATES = [
    {"name": "Selorm Mensah", "email": "selorm.mensah@example.com", "phone": "+233245500101"},
    {"name": "Efua Brown", "email": "efua.brown@example.com", "phone": "+233245500102"},
    {"name": "Kofi Ampah", "email": "kofi.ampah@example.com", "phone": "+233245500103"},
    {"name": "Mariam Yakubu", "email": "mariam.yakubu@example.com", "phone": "+233245500104"},
    {"name": "Yaw Frimpong", "email": "yaw.frimpong@example.com", "phone": "+233245500105"},
    {"name": "Abena Sika", "email": "abena.sika@example.com", "phone": "+233245500106"},
    {"name": "Prince Koomson", "email": "prince.koomson@example.com", "phone": "+233245500107"},
]

SUPPLIER_TEMPLATES = [
    {
        "name": "Citrus Valley Imports",
        "contact_person": "Amelia Mensah",
        "email": "orders@citrusvalley.example.com",
        "phone_number": "+233302555111",
        "address": "12 Citrus Lane, Tema",
    },
    {
        "name": "Northern Agro Traders",
        "contact_person": "Kojo Aning",
        "email": "sales@northernagro.example.com",
        "phone_number": "+233244660011",
        "address": "57 Sagnerigu Road, Tamale",
    },
    {
        "name": "BlueWave Wholesale",
        "contact_person": "Dorothy Larbi",
        "email": "hello@bluewavewholesale.example.com",
        "phone_number": "+233202880045",
        "address": "88 Ring Road Central, Accra",
    },
    {
        "name": "Everfresh Dairy Co.",
        "contact_person": "Samuel Nkrumah",
        "email": "support@everfreshdairy.example.com",
        "phone_number": "+233501220077",
        "address": "5 Cocoa Avenue, Kumasi",
    },
    {
        "name": "Household Hub Supplies",
        "contact_person": "Grace Abbey",
        "email": "contact@householdhub.example.com",
        "phone_number": "+233208665432",
        "address": "34 Spintex Road, Accra",
    },
    {
        "name": "Sunrise Provision Store",
        "contact_person": "Yaw Kusi",
        "email": "info@sunriseprovisions.example.com",
        "phone_number": "+233245778899",
        "address": "14 Axim Road, Takoradi",
    },
    {
        "name": "Prime Snacks Distributors",
        "contact_person": "Matilda Aidoo",
        "email": "orders@primesnacks.example.com",
        "phone_number": "+233205551234",
        "address": "21 Asafoatse Lane, Accra",
    },
    {
        "name": "Global Beverage Partners",
        "contact_person": "Nana Owusu",
        "email": "sales@globalbevpartners.example.com",
        "phone_number": "+233209901212",
        "address": "101 Independence Ave, Accra",
    },
]

PASSWORD_TEMPLATE = "DemoPass123!"


class Command(BaseCommand):
    help = (
        "Seed the database with demo data including businesses, warehouses, storefronts, "
        "inventory, sales, and subscription artefacts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owners",
            type=int,
            default=5,
            help="Number of business owners to seed (default: 5).",
        )
        parser.add_argument(
            "--max-warehouses",
            type=int,
            default=3,
            help="Maximum warehouses per business (default: 3).",
        )
        parser.add_argument(
            "--max-storefronts",
            type=int,
            default=6,
            help="Maximum storefronts per business (default: 6).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Create new demo records even if businesses already exist.",
        )

    def handle(self, *args, **options):
        random.seed(42)
        owners_to_create = options["owners"]
        max_warehouses = max(1, options["max_warehouses"])
        max_storefronts = max(1, options["max_storefronts"])
        force = options["force"]

        existing_businesses = Business.objects.count()
        if existing_businesses > 0 and not force:
            self.stdout.write(
                self.style.WARNING(
                    f"Database already contains {existing_businesses} businesses. "
                    "Use --force to append new demo data."
                )
            )
            return

        self.stdout.write(self.style.NOTICE("Preparing reference data..."))
        roles = self._ensure_roles()
        categories = self._ensure_categories()
        products = self._ensure_products(categories)
        plan = self._ensure_subscription_plan()

        blueprints = BUSINESS_BLUEPRINTS[:owners_to_create]
        if len(blueprints) < owners_to_create:
            self.stdout.write(
                self.style.WARNING(
                    "Requested owners exceed predefined templates; using available templates only."
                )
            )

        for index, blueprint in enumerate(blueprints, start=1):
            with transaction.atomic():
                self.stdout.write(self.style.NOTICE(f"\nSeeding business {index}: {blueprint['business_name']}"))
                owner = self._create_owner_user(blueprint, roles)
                business = self._create_business(blueprint, owner)
                warehouses = self._create_warehouses(business, owner, max_warehouses)
                storefronts = self._create_storefronts(business, owner, max_storefronts)
                stock_lots = self._stock_warehouses(business, warehouses, products)
                customers = self._create_customers(business, owner)
                self._generate_sales_activity(business, owner, storefronts, stock_lots, customers)
                self._create_transfers_and_alerts(business, owner, warehouses, storefronts, stock_lots)
                self._setup_subscription_records(business, owner, plan)

        self.stdout.write(self.style.SUCCESS("Demo data seeding complete."))

    # --- reference data helpers -------------------------------------------------

    def _ensure_roles(self):
        roles = {}
        for name in ["Admin", "Manager", "Cashier", "Warehouse Staff"]:
            role, _ = Role.objects.get_or_create(name=name, defaults={"description": f"{name} role"})
            roles[name] = role
        return roles

    def _ensure_categories(self):
        categories = {}
        for name, description in CATEGORY_DATA:
            category, _ = Category.objects.get_or_create(name=name, defaults={"description": description})
            categories[name] = category
        return categories

    def _ensure_products(self, categories):
        products = []
        for data in PRODUCT_DATA:
            category = categories[data["category"]]
            product, _ = Product.objects.get_or_create(
                sku=data["sku"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "category": category,
                    "unit": data["unit"],
                    "retail_price": data["retail_price"],
                    "wholesale_price": data["wholesale_price"],
                    "cost": data["cost"],
                },
            )
            products.append(product)
        return products

    def _ensure_subscription_plan(self):
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Premium Retail",
            defaults={
                "description": "Full feature plan seeded for demo data.",
                "price": Decimal("499.00"),
                "billing_cycle": "MONTHLY",
                "max_users": 50,
                "max_storefronts": 10,
                "max_products": 10000,
                "max_transactions_per_month": 50000,
                "features": [
                    "Inventory Valuation Reports",
                    "Multi-store Management",
                    "Advanced Analytics",
                    "Priority Support",
                ],
            },
        )
        return plan

    # --- business creation helpers ---------------------------------------------

    def _create_owner_user(self, blueprint, roles):
        email = blueprint["email"]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": blueprint["owner_name"],
                "role": roles["Admin"],
                "subscription_status": "Active",
            },
        )
        if created:
            user.set_password(PASSWORD_TEMPLATE)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"  Created owner account {email}"))
        else:
            self.stdout.write(self.style.WARNING(f"  Owner account {email} already existed"))
        return user

    def _create_business(self, blueprint, owner):
        business, created = Business.objects.get_or_create(
            name=blueprint["business_name"],
            defaults={
                "owner": owner,
                "tin": blueprint["tin"],
                "website": blueprint["website"],
                "email": blueprint["email"],
                "address": blueprint["address"],
                "phone_numbers": blueprint["phones"],
                "social_handles": blueprint["social"],
                "is_active": True,
            },
        )
        if not created:
            business.owner = owner
            business.email = blueprint["email"]
            business.address = blueprint["address"]
            business.phone_numbers = blueprint["phones"]
            business.social_handles = blueprint["social"]
            business.website = blueprint["website"]
            business.save()
            self.stdout.write(self.style.WARNING(f"  Business {business.name} already existed; updated owner info."))
        else:
            self.stdout.write(self.style.SUCCESS(f"  Created business {business.name}"))

        membership, _ = BusinessMembership.objects.get_or_create(
            business=business,
            user=owner,
            defaults={"role": BusinessMembership.OWNER, "is_admin": True, "is_active": True},
        )
        if membership.role != BusinessMembership.OWNER:
            membership.role = BusinessMembership.OWNER
            membership.is_admin = True
            membership.is_active = True
            membership.save()
        return business

    def _create_warehouses(self, business, owner, max_warehouses):
        warehouse_count = min(max_warehouses, random.randint(2, max_warehouses))
        warehouses = []
        for idx in range(warehouse_count):
            name = f"{business.name.split()[0]} Warehouse {idx + 1}"
            location = random.choice(WAREHOUSE_LOCATIONS)
            warehouse, created = Warehouse.objects.get_or_create(
                name=name,
                defaults={"location": location, "manager": owner},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"    Added warehouse: {name}"))
            else:
                warehouse.location = location
                warehouse.manager = owner
                warehouse.save()
                self.stdout.write(self.style.WARNING(f"    Reused existing warehouse: {name}"))

            BusinessWarehouse.objects.get_or_create(business=business, warehouse=warehouse)
            WarehouseEmployee.objects.get_or_create(
                business=business,
                warehouse=warehouse,
                user=owner,
                defaults={"role": BusinessMembership.OWNER, "is_active": True},
            )
            warehouses.append(warehouse)
        return warehouses

    def _create_storefronts(self, business, owner, max_storefronts):
        storefront_count = min(max_storefronts, random.randint(3, max_storefronts))
        storefronts = []
        for idx in range(storefront_count):
            name = f"{business.name.split()[0]} Store {idx + 1}"
            location = random.choice(STOREFRONT_LOCATIONS)
            storefront, created = StoreFront.objects.get_or_create(
                name=name,
                defaults={"user": owner, "location": location, "manager": owner},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"    Added storefront: {name}"))
            else:
                storefront.user = owner
                storefront.location = location
                storefront.manager = owner
                storefront.save()
                self.stdout.write(self.style.WARNING(f"    Reused existing storefront: {name}"))

            BusinessStoreFront.objects.get_or_create(business=business, storefront=storefront)
            StoreFrontEmployee.objects.get_or_create(
                business=business,
                storefront=storefront,
                user=owner,
                defaults={"role": BusinessMembership.OWNER, "is_active": True},
            )
            storefronts.append(storefront)
        return storefronts

    # --- inventory helpers -----------------------------------------------------

    def _stock_warehouses(self, business, warehouses, products):
        inventory_summary = {}
        supplier_cache: dict[str, Supplier] = {}
        today = timezone.now().date()

        for warehouse in warehouses:
            warehouse_entry = inventory_summary.setdefault(warehouse.id, {})
            for product in products:
                lots = warehouse_entry.setdefault(product.id, [])
                lot_count = random.randint(2, 3)
                for lot_index in range(1, lot_count + 1):
                    supplier_template = random.choice(SUPPLIER_TEMPLATES)
                    supplier = self._get_or_create_supplier(supplier_template, supplier_cache)
                    arrival_offset = random.randint(20, 160)
                    arrival_date = today - timedelta(days=arrival_offset)
                    expiry_date = arrival_date + timedelta(days=random.randint(180, 720))

                    reference_code = self._generate_reference(product.sku, warehouse.id)
                    stock_batch = Stock.objects.create(
                        warehouse=warehouse,
                        supplier=supplier,
                        reference_code=reference_code,
                        arrival_date=arrival_date,
                        description=f"Receipt lot {lot_index} for {product.name}",
                    )

                    base_cost = product.cost or Decimal("10.00")
                    cost_variation = Decimal(random.uniform(-2.50, 8.75)).quantize(Decimal("0.01"))
                    unit_cost = max(Decimal("1.00"), base_cost + cost_variation)
                    tax_rate = Decimal(random.choice([0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0])).quantize(Decimal("0.01"))
                    unit_tax_amount = ((unit_cost * tax_rate) / Decimal("100.00")).quantize(Decimal("0.01"))
                    unit_additional_cost = Decimal(random.uniform(0.25, 5.75)).quantize(Decimal("0.01"))
                    quantity = random.randint(25, 100)

                    stock_product = StockProduct.objects.create(
                        stock=stock_batch,
                        warehouse=warehouse,
                        product=product,
                        supplier=supplier,
                        supplier_name=supplier.name,
                        reference_code=f"{reference_code}-LOT{lot_index}",
                        arrival_date=arrival_date,
                        expiry_date=expiry_date,
                        quantity=quantity,
                        unit_cost=unit_cost,
                        unit_tax_rate=tax_rate,
                        unit_tax_amount=unit_tax_amount,
                        unit_additional_cost=unit_additional_cost,
                        description=f"Lot {lot_index} for {product.name} from {supplier.name}",
                    )

                    inventory_entry, _ = Inventory.objects.get_or_create(
                        product=product,
                        stock=stock_product,
                        warehouse=warehouse,
                        defaults={"quantity": quantity},
                    )
                    inventory_entry.quantity = quantity
                    inventory_entry.save()

                    lots.append(
                        {
                            "stock": stock_batch,
                            "stock_product": stock_product,
                            "inventory": inventory_entry,
                            "available_quantity": quantity,
                        }
                    )
        return inventory_summary

    def _create_customers(self, business, owner):
        customers = []
        for tpl in CUSTOMER_TEMPLATES:
            name = tpl["name"]
            email = tpl["email"].replace("@", f"+{business.id}@")
            phone = tpl["phone"][:-1] + str(random.randint(0, 9))
            customer, _ = Customer.objects.get_or_create(
                name=name,
                defaults={
                    "email": email,
                    "phone": phone,
                    "address": business.address,
                    "credit_limit": Decimal("1500.00"),
                    "created_by": owner,
                },
            )
            customers.append(customer)
        return customers

    def _generate_sales_activity(self, business, owner, storefronts, inventory_summary, customers):
        if not storefronts or not customers:
            return

        receipt_index = 1
        for storefront in storefronts:
            customer_count = min(len(customers), max(1, random.randint(1, 3)))
            store_customers = random.sample(customers, customer_count)
            for customer in store_customers:
                receipt_number = f"{business.name[:3].upper()}-{storefront.id.hex[:4]}-{receipt_index:04d}"
                sale = Sale.objects.create(
                    storefront=storefront,
                    user=owner,
                    customer=customer,
                    total_amount=Decimal("0.00"),
                    payment_type=random.choice(["CARD", "CASH", "MOBILE", "CREDIT", "MIXED"]),
                    status="COMPLETED",
                    type=random.choice(["RETAIL", "WHOLESALE"]),
                    amount_due=Decimal("0.00"),
                    discount_amount=Decimal("0.00"),
                    tax_amount=Decimal("0.00"),
                    receipt_number=receipt_number,
                    notes="Demo sale seeded for reporting",
                )

                line_count = random.randint(2, 4)
                sale_total = Decimal("0.00")
                line_tax_total = Decimal("0.00")

                for _ in range(line_count):
                    selection = self._pick_available_lot(inventory_summary)
                    if not selection:
                        break

                    warehouse_id, product_id, lot_info = selection
                    stock_product = lot_info["stock_product"]
                    inventory_entry = lot_info["inventory"]
                    if lot_info["available_quantity"] <= 0:
                        continue

                    max_quantity = min(lot_info["available_quantity"], random.randint(1, 6))
                    if max_quantity <= 0:
                        continue

                    quantity = random.randint(1, max_quantity)
                    product = stock_product.product
                    unit_price = product.retail_price or product.wholesale_price or product.cost or Decimal("0.00")
                    discount = Decimal(random.choice([0, 1.5, 2.5, 5.0])).quantize(Decimal("0.01"))
                    tax_rate = stock_product.unit_tax_rate

                    sale_item = SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        stock=stock_product,
                        quantity=quantity,
                        unit_price=unit_price,
                        discount_amount=discount,
                        tax_rate=tax_rate,
                    )
                    sale_item.save()

                    lot_info["available_quantity"] -= quantity
                    inventory_entry.quantity = max(0, inventory_entry.quantity - quantity)
                    inventory_entry.save()

                    sale_total += sale_item.total_price
                    line_tax_total += sale_item.tax_amount

                    if lot_info["available_quantity"] <= 0:
                        inventory_summary[warehouse_id][product_id] = [
                            lot for lot in inventory_summary[warehouse_id][product_id] if lot["available_quantity"] > 0
                        ]

                if sale_total == Decimal("0.00"):
                    sale.delete()
                    continue

                sale.tax_amount = line_tax_total
                sale.total_amount = sale_total
                sale.amount_due = Decimal("0.00")
                sale.save()

                Payment.objects.create(
                    sale=sale,
                    customer=customer,
                    amount_paid=sale_total,
                    payment_method=random.choice(["CASH", "CARD", "MOMO", "BANK_TRANSFER"]),
                    status="SUCCESSFUL",
                )

                CreditTransaction.objects.create(
                    customer=customer,
                    transaction_type=random.choice(["PAYMENT", "CREDIT_SALE"]),
                    amount=sale_total,
                    balance_before=Decimal("0.00"),
                    balance_after=Decimal("0.00"),
                    reference_id=sale.id,
                    description=f"Auto-generated transaction for {sale.receipt_number}",
                    created_by=owner,
                )

                receipt_index += 1

    def _create_transfers_and_alerts(self, business, owner, warehouses, storefronts, inventory_summary):
        if not warehouses or not storefronts or not inventory_summary:
            return

        source_warehouse = warehouses[0]
        target_storefront = storefronts[0]
        warehouse_lots = inventory_summary.get(source_warehouse.id)
        if not warehouse_lots:
            return

        product_id, lots = random.choice(list(warehouse_lots.items()))
        if not lots:
            return

        lot_info = lots[0]
        stock_product = lot_info["stock_product"]
        product = stock_product.product
        quantity = min(10, max(1, lot_info["available_quantity"]))

        Transfer.objects.get_or_create(
            product=product,
            stock=stock_product,
            from_warehouse=source_warehouse,
            to_storefront=target_storefront,
            defaults={
                "quantity": quantity,
                "status": "COMPLETED",
                "requested_by": owner,
                "approved_by": owner,
                "note": "Demo transfer for seeded data",
            },
        )

        current_quantity = sum(lot["available_quantity"] for lot in lots)
        StockAlert.objects.get_or_create(
            product=product,
            warehouse=source_warehouse,
            alert_type="LOW_STOCK",
            defaults={
                "current_quantity": current_quantity,
                "threshold_quantity": max(5, quantity // 2),
                "is_resolved": False,
            },
        )

    # --- subscription helpers --------------------------------------------------

    def _setup_subscription_records(self, business, owner, plan):
        start_date = timezone.now().date() - timedelta(days=15)
        end_date = start_date + timedelta(days=plan.get_billing_days())

        subscription, created = Subscription.objects.get_or_create(
            user=owner,
            plan=plan,
            defaults={
                "amount": plan.price,
                "payment_method": "STRIPE",
                "payment_status": "PAID",
                "status": "ACTIVE",
                "start_date": start_date,
                "end_date": end_date,
                "auto_renew": True,
                "next_billing_date": end_date,
                "is_trial": False,
            },
        )
        if not created:
            subscription.amount = plan.price
            subscription.status = "ACTIVE"
            subscription.payment_status = "PAID"
            subscription.start_date = start_date
            subscription.end_date = end_date
            subscription.next_billing_date = end_date
            subscription.save()

        SubscriptionPayment.objects.get_or_create(
            subscription=subscription,
            amount=plan.price,
            payment_method="STRIPE",
            status="SUCCESSFUL",
            billing_period_start=start_date,
            billing_period_end=end_date,
            defaults={
                "transaction_id": self._random_code(prefix="PAY"),
                "payment_date": timezone.now(),
            },
        )

        Invoice.objects.get_or_create(
            subscription=subscription,
            invoice_number=self._random_code(prefix="INV"),
            defaults={
                "amount": plan.price,
                "tax_amount": plan.price * Decimal("0.18"),
                "total_amount": plan.price * Decimal("1.18"),
                "status": "PAID",
                "issue_date": start_date,
                "due_date": start_date + timedelta(days=7),
                "paid_date": start_date + timedelta(days=2),
                "billing_period_start": start_date,
                "billing_period_end": end_date,
                "notes": f"Automated invoice for {business.name}",
            },
        )

    # --- utility ---------------------------------------------------------------

    def _generate_reference(self, sku, warehouse_id):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{sku}-{str(warehouse_id)[:4]}-{suffix}"

    def _random_code(self, prefix="REF"):
        return f"{prefix}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

    def _get_or_create_supplier(self, template, cache):
        supplier = cache.get(template["name"])
        if supplier:
            return supplier

        supplier, _ = Supplier.objects.get_or_create(
            name=template["name"],
            defaults={
                "contact_person": template.get("contact_person"),
                "email": template.get("email"),
                "phone_number": template.get("phone_number"),
                "address": template.get("address"),
            },
        )
        cache[template["name"]] = supplier
        return supplier

    def _pick_available_lot(self, inventory_summary):
        candidates = []
        for warehouse_id, product_map in inventory_summary.items():
            for product_id, lots in product_map.items():
                for lot in lots:
                    if lot["available_quantity"] > 0:
                        candidates.append((warehouse_id, product_id, lot))
        if not candidates:
            return None
        return random.choice(candidates)