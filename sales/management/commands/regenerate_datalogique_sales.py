import random
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Business
from inventory.models import (
    Category,
    Product,
    StoreFront,
    BusinessStoreFront,
    Warehouse,
    Supplier,
    Stock,
    StockProduct,
    Inventory,
    StoreFrontInventory,
    BusinessWarehouse,
)
from sales.models import Customer, Payment, Sale, SaleItem


TWO_PLACES = Decimal("0.01")
BUSINESS_NAME = "DataLogique Systems"

PRODUCT_TEMPLATES = [
    {"name": "Thermal Receipt Printer", "sku": "DL-TRP-001", "category": "POS Hardware", "unit": "pcs", "price": "350.00"},
    {"name": "Barcode Scanner", "sku": "DL-BSC-002", "category": "POS Hardware", "unit": "pcs", "price": "210.00"},
    {"name": "Touchscreen POS Terminal", "sku": "DL-POS-003", "category": "POS Hardware", "unit": "pcs", "price": "1450.00"},
    {"name": "Cash Drawer", "sku": "DL-CSD-004", "category": "Store Accessories", "unit": "pcs", "price": "185.00"},
    {"name": "Receipt Paper Roll (20 pack)", "sku": "DL-PPR-005", "category": "Consumables", "unit": "pack", "price": "48.00"},
    {"name": "Customer Display", "sku": "DL-CDS-006", "category": "Store Accessories", "unit": "pcs", "price": "265.00"},
    {"name": "Inventory Tablet", "sku": "DL-TAB-007", "category": "Mobility", "unit": "pcs", "price": "520.00"},
    {"name": "Label Printer", "sku": "DL-LBL-008", "category": "POS Hardware", "unit": "pcs", "price": "315.00"},
    {"name": "Wireless Router", "sku": "DL-ROU-009", "category": "Networking", "unit": "pcs", "price": "165.00"},
    {"name": "Back-Office Software License", "sku": "DL-SFT-010", "category": "Software", "unit": "license", "price": "780.00"},
]

CUSTOMER_TEMPLATES = [
    {"name": "Walk-in Customer", "type": "RETAIL", "email": "", "phone": "000-000-0000", "credit_limit": "0.00", "terms": 0},
    {"name": "Accra Retail Hub", "type": "WHOLESALE", "email": "accounts@accretailhub.com", "phone": "+233-240-111-222", "credit_limit": "15000.00", "terms": 45},
    {"name": "Metro Convenience", "type": "RETAIL", "email": "finance@metroconvenience.com", "phone": "+233-240-333-444", "credit_limit": "6000.00", "terms": 30},
    {"name": "Sunrise Mini Mart", "type": "WHOLESALE", "email": "hello@sunriseminimart.com", "phone": "+233-240-555-666", "credit_limit": "8000.00", "terms": 30},
    {"name": "Blue Skies Boutique", "type": "RETAIL", "email": "ops@blueskiesboutique.com", "phone": "+233-240-777-888", "credit_limit": "3500.00", "terms": 21},
    {"name": "Campus Express", "type": "WHOLESALE", "email": "payments@campusexpress.com", "phone": "+233-240-999-000", "credit_limit": "12000.00", "terms": 40},
]

PAYMENT_METHOD_MAP = {
    "CASH": "CASH",
    "CARD": "CARD",
    "MOBILE": "MOMO",
    "CREDIT": "BANK_TRANSFER",
}


def money(value: Decimal | str | float) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def build_payment_plan(total: Decimal, *, min_parts: int = 1, max_parts: int = 3) -> list[Decimal]:
    """Split a total into random instalments that sum back to the total."""
    total = total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if total <= Decimal("0.00"):
        return []

    parts = max(min_parts, 1)
    if max_parts > min_parts:
        parts = random.randint(min_parts, max_parts)

    allocations: list[Decimal] = []
    remaining = total

    for idx in range(parts, 1, -1):
        # Aim for reasonably sized instalments (20%-70% of remaining)
        lower = float(Decimal("0.20"))
        upper = float(Decimal("0.70"))
        proposed = remaining * Decimal(str(random.uniform(lower, upper)))
        amount = proposed.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Ensure the amount stays within bounds and leaves room for remaining parts
        min_remaining = (Decimal("0.05") * remaining).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if amount <= Decimal("0.00") or remaining - amount < min_remaining:
            amount = (remaining / Decimal(idx)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        if amount >= remaining:
            amount = (remaining / Decimal(idx)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        allocations.append(amount)
        remaining -= amount

    allocations.append(remaining.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))

    # Fix potential rounding drift on last payment
    diff = total - sum(allocations)
    if diff != Decimal("0.00"):
        allocations[-1] = (allocations[-1] + diff).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return [amount for amount in allocations if amount > Decimal("0.00")]


class ReceiptNumberGenerator:
    def __init__(self, prefix: str = "DL"):
        self.prefix = prefix
        self._seen: set[str] = set()

    def next(self, sale_dt) -> str:
        for _ in range(20):
            candidate = f"{self.prefix}-{sale_dt.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            if candidate not in self._seen:
                self._seen.add(candidate)
                return candidate
        raise RuntimeError("Unable to generate unique receipt number")


def ensure_storefront(business) -> StoreFront:
    link = BusinessStoreFront.objects.filter(business=business, is_active=True).select_related("storefront").first()
    if link:
        return link.storefront

    owner = business.owner
    storefront = StoreFront.objects.create(
        user=owner,
        name="DataLogique Flagship Store",
        location="48 Independence Avenue, Accra",
    )
    BusinessStoreFront.objects.create(business=business, storefront=storefront, is_active=True)
    return storefront


def ensure_products(business):
    catalog = []
    for template in PRODUCT_TEMPLATES:
        category, _ = Category.objects.get_or_create(
            name=template["category"],
            defaults={"description": f"{template['category']} offerings"},
        )

        product, created = Product.objects.get_or_create(
            business=business,
            name=template["name"],
            defaults={
                "sku": template["sku"],
                "category": category,
                "unit": template.get("unit", "pcs"),
                "description": template["name"],
            },
        )
        if not created and product.category_id != category.id:
            product.category = category
            product.save(update_fields=["category"])

        catalog.append((product, money(template["price"])))
    return catalog


def ensure_customers(business, creator):
    customers = []
    for template in CUSTOMER_TEMPLATES:
        customer, created = Customer.objects.get_or_create(
            business=business,
            name=template["name"],
            defaults={
                "customer_type": template["type"],
                "email": template["email"],
                "phone": template["phone"],
                "created_by": creator,
                "credit_limit": money(template["credit_limit"]),
                "credit_terms_days": template["terms"],
            },
        )

        updated_fields = []
        if customer.customer_type != template["type"]:
            customer.customer_type = template["type"]
            updated_fields.append("customer_type")
        if customer.credit_limit != money(template["credit_limit"]):
            customer.credit_limit = money(template["credit_limit"])
            updated_fields.append("credit_limit")
        if customer.credit_terms_days != template["terms"]:
            customer.credit_terms_days = template["terms"]
            updated_fields.append("credit_terms_days")
        if customer.phone != template["phone"]:
            customer.phone = template["phone"]
            updated_fields.append("phone")
        if customer.email != template["email"]:
            customer.email = template["email"]
            updated_fields.append("email")
        if created and customer.created_by_id != getattr(creator, "id", None):
            customer.created_by = creator
            updated_fields.append("created_by")

        customer.outstanding_balance = Decimal("0.00")
        updated_fields.append("outstanding_balance")
        customer.credit_blocked = False
        updated_fields.append("credit_blocked")
        customer.is_active = True
        updated_fields.append("is_active")
        customer.save(update_fields=list(dict.fromkeys(updated_fields)))
        customers.append(customer)
    return customers


def ensure_inventory(business, storefront, products):
    owner = business.owner
    warehouse, _ = Warehouse.objects.get_or_create(
        name="DataLogique Central Warehouse",
        location="Tema Logistics Hub",
        defaults={"manager": owner},
    )
    if warehouse.manager_id != getattr(owner, "id", None):
        warehouse.manager = owner
        warehouse.save(update_fields=["manager", "updated_at"])

    BusinessWarehouse.objects.get_or_create(business=business, warehouse=warehouse)

    supplier, _ = Supplier.objects.get_or_create(
        business=business,
        name="DataLogique Preferred Supplier",
        defaults={
            "contact_person": "Procurement Desk",
            "phone_number": "+233-240-100-200",
            "email": "procurement@datalogique.com",
        },
    )

    today = timezone.now().date()

    for product, retail_price in products:
        stock_product = StockProduct.objects.filter(
            product=product,
            stock__warehouse=warehouse,
        ).order_by("-created_at").first()

        if stock_product:
            updates = []
            if stock_product.retail_price != retail_price:
                stock_product.retail_price = retail_price
                updates.append("retail_price")
            if not stock_product.wholesale_price or stock_product.wholesale_price == Decimal("0.00"):
                stock_product.wholesale_price = (retail_price * Decimal("0.90")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                updates.append("wholesale_price")
            if stock_product.quantity <= 0:
                stock_product.quantity = random.randint(60, 140)
                updates.append("quantity")
            if updates:
                stock_product.save(update_fields=updates + ["updated_at"])
        else:
            stock_batch = Stock.objects.create(
                warehouse=warehouse,
                arrival_date=today - timedelta(days=random.randint(5, 45)),
                description=f"Initial intake for {product.name}",
            )
            quantity = random.randint(60, 140)
            unit_cost = (retail_price * Decimal(str(random.uniform(0.45, 0.65)))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            stock_product = StockProduct.objects.create(
                stock=stock_batch,
                product=product,
                supplier=supplier,
                expiry_date=today + timedelta(days=random.randint(180, 540)),
                quantity=quantity,
                unit_cost=unit_cost,
                retail_price=retail_price,
                wholesale_price=(retail_price * Decimal("0.90")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                description="Seeded inventory for demo dataset",
            )

        Inventory.objects.update_or_create(
            product=product,
            warehouse=warehouse,
            stock=stock_product,
            defaults={"quantity": stock_product.quantity},
        )

        store_qty = max(20, min(stock_product.quantity, int(stock_product.quantity * 0.7)))
        StoreFrontInventory.objects.update_or_create(
            storefront=storefront,
            product=product,
            defaults={"quantity": store_qty},
        )


def create_sale_with_items(*, sale_date, business, storefront, user, customer, products, receipt_gen):
    sale = Sale.objects.create(
        business=business,
        storefront=storefront,
        user=user,
        customer=customer,
        status="DRAFT",
        payment_type="CASH",
        type="WHOLESALE" if customer.customer_type == "WHOLESALE" else "RETAIL",
    )

    line_count = random.randint(1, 4)
    chosen_products = random.sample(products, line_count)

    for product, unit_price in chosen_products:
        quantity = Decimal(random.randint(1, 5))
        discount_percentage = Decimal("0.00")
        if random.random() < 0.20:
            discount_percentage = Decimal(random.choice(["5.00", "7.50", "10.00"]))

        tax_rate = Decimal("12.50") if random.random() < 0.65 else Decimal("0.00")

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            discount_percentage=discount_percentage,
            tax_rate=tax_rate,
        )

    sale.discount_amount = Decimal("0.00")
    sale.tax_amount = Decimal("0.00")
    sale.amount_paid = Decimal("0.00")
    sale.calculate_totals()
    sale.save(update_fields=[
        "discount_amount",
        "tax_amount",
        "subtotal",
        "total_amount",
        "amount_due",
    ])

    # Snapshot times after totals calculated
    Sale.objects.filter(pk=sale.pk).update(created_at=sale_date, updated_at=sale_date)
    sale.refresh_from_db()

    sale.receipt_number = receipt_gen.next(sale_date)
    return sale


def finalise_completed_sale(sale, *, payment_method, sale_date, processed_by, credit: bool = False, payment_plan: list[Decimal] | None = None):
    sale.payment_type = 'CREDIT' if credit else payment_method
    sale.calculate_totals()
    sale.amount_paid = sale.total_amount
    sale.calculate_totals()
    sale.status = "COMPLETED"
    sale.completed_at = sale_date
    sale.save(update_fields=[
        "payment_type",
        "amount_paid",
        "subtotal",
        "total_amount",
        "amount_due",
        "status",
        "completed_at",
        "receipt_number",
    ])

    if credit:
        instalments = payment_plan or [sale.total_amount]
        running_date = sale_date
        for amount in instalments:
            payment = Payment.objects.create(
                sale=sale,
                customer=sale.customer,
                amount_paid=amount,
                payment_method=PAYMENT_METHOD_MAP.get("CREDIT", "BANK_TRANSFER"),
                processed_by=processed_by,
            )
            Payment.objects.filter(pk=payment.pk).update(
                payment_date=running_date,
                created_at=running_date,
                updated_at=running_date,
            )
            running_date += timedelta(days=random.randint(2, 7))
    else:
        payment = Payment.objects.create(
            sale=sale,
            customer=sale.customer,
            amount_paid=sale.total_amount,
            payment_method=PAYMENT_METHOD_MAP.get(payment_method, "CASH"),
            processed_by=processed_by,
        )
        Payment.objects.filter(pk=payment.pk).update(payment_date=sale_date, created_at=sale_date, updated_at=sale_date)


def finalise_partial_sale(sale, *, sale_date, processed_by, outstanding_tracker):
    sale.payment_type = "CREDIT"
    sale.calculate_totals()
    paid_fraction = Decimal(str(random.uniform(0.45, 0.75)))
    amount_paid = (sale.total_amount * paid_fraction).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    sale.amount_paid = amount_paid
    sale.calculate_totals()
    sale.status = "PARTIAL"
    sale.completed_at = sale_date
    sale.save(update_fields=[
        "payment_type",
        "amount_paid",
        "subtotal",
        "total_amount",
        "amount_due",
        "status",
        "completed_at",
        "receipt_number",
    ])

    outstanding_tracker[sale.customer_id] += sale.amount_due

    instalments = build_payment_plan(amount_paid, min_parts=1, max_parts=2)
    if not instalments:
        instalments = [amount_paid]

    running_date = sale_date
    for amount in instalments:
        payment = Payment.objects.create(
            sale=sale,
            customer=sale.customer,
            amount_paid=amount,
            payment_method=random.choice(["CASH", "MOMO", "CARD", "BANK_TRANSFER"]),
            processed_by=processed_by,
        )
        Payment.objects.filter(pk=payment.pk).update(
            payment_date=running_date,
            created_at=running_date,
            updated_at=running_date,
        )
        running_date += timedelta(days=random.randint(3, 10))


def finalise_pending_sale(sale, *, sale_date, outstanding_tracker):
    sale.payment_type = "CREDIT"
    sale.calculate_totals()
    sale.amount_paid = Decimal("0.00")
    sale.calculate_totals()
    sale.status = "PENDING"
    sale.completed_at = sale_date
    sale.save(update_fields=[
        "payment_type",
        "amount_paid",
        "subtotal",
        "total_amount",
        "amount_due",
        "status",
        "completed_at",
        "receipt_number",
    ])

    outstanding_tracker[sale.customer_id] += sale.amount_due


def leave_as_draft(sale):
    sale.payment_type = random.choice(["CASH", "CARD", "MOBILE"])
    sale.status = "DRAFT"
    sale.calculate_totals()
    sale.amount_paid = Decimal("0.00")
    sale.calculate_totals()
    sale.completed_at = None
    sale.receipt_number = None
    sale.save(update_fields=[
        "payment_type",
        "amount_paid",
        "subtotal",
        "total_amount",
        "amount_due",
        "status",
        "completed_at",
        "receipt_number",
    ])


def regenerate_sales_dataset(*, business, storefront, user, products, customers, counts):
    Sale.objects.filter(business=business).delete()
    Payment.objects.filter(customer__business=business).delete()

    outstanding_tracker = defaultdict(lambda: Decimal("0.00"))
    receipt_gen = ReceiptNumberGenerator(prefix="DLGS")
    now = timezone.now()

    status_order = [
        ("COMPLETED", counts.get("completed", 80)),
        ("PARTIAL", counts.get("partial", 20)),
        ("PENDING", counts.get("pending", 12)),
        ("DRAFT", counts.get("draft", 12)),
    ]

    sales_created = {
        "COMPLETED": [],
        "PARTIAL": [],
        "PENDING": [],
        "DRAFT": [],
    }

    for status, target_count in status_order:
        for _ in range(target_count):
            sale_date = now - timedelta(days=random.randint(3, 150), hours=random.randint(0, 10), minutes=random.randint(0, 59))
            customer_pool = customers
            if status in {"PARTIAL", "PENDING"}:
                credit_customers = [c for c in customers if c.credit_limit > Decimal("0.00")]
                if credit_customers:
                    customer_pool = credit_customers
            customer = random.choice(customer_pool)

            sale = create_sale_with_items(
                sale_date=sale_date,
                business=business,
                storefront=storefront,
                user=user,
                customer=customer,
                products=products,
                receipt_gen=receipt_gen,
            )

            if status == "COMPLETED":
                should_be_credit = customer.credit_limit > Decimal("0.00") and random.random() < 0.35
                if should_be_credit:
                    payment_plan = build_payment_plan(sale.total_amount, min_parts=1, max_parts=3)
                    finalise_completed_sale(
                        sale,
                        payment_method="CREDIT",
                        sale_date=sale_date,
                        processed_by=user,
                        credit=True,
                        payment_plan=payment_plan,
                    )
                else:
                    finalise_completed_sale(
                        sale,
                        payment_method=random.choice(["CASH", "CARD", "MOBILE"]),
                        sale_date=sale_date,
                        processed_by=user,
                    )
            elif status == "PARTIAL":
                finalise_partial_sale(
                    sale,
                    sale_date=sale_date,
                    processed_by=user,
                    outstanding_tracker=outstanding_tracker,
                )
            elif status == "PENDING":
                finalise_pending_sale(
                    sale,
                    sale_date=sale_date,
                    outstanding_tracker=outstanding_tracker,
                )
            else:
                leave_as_draft(sale)

            Sale.objects.filter(pk=sale.pk).update(created_at=sale_date, updated_at=sale_date, completed_at=sale.completed_at)
            sales_created[status].append(sale.id)

    # Update customer balances
    for customer in customers:
        new_balance = outstanding_tracker[customer.id]
        if customer.outstanding_balance != new_balance:
            customer.outstanding_balance = new_balance
            customer.save(update_fields=["outstanding_balance"])

    return {status: len(ids) for status, ids in sales_created.items()}


class Command(BaseCommand):
    help = "Delete existing DataLogique sales and generate a realistic dataset"

    def add_arguments(self, parser):
        parser.add_argument("--completed", type=int, default=85, help="Number of completed sales to generate")
        parser.add_argument("--partial", type=int, default=25, help="Number of partial credit sales")
        parser.add_argument("--pending", type=int, default=15, help="Number of pending credit sales")
        parser.add_argument("--draft", type=int, default=15, help="Number of open draft carts")
        parser.add_argument("--seed", type=int, default=42, help="Seed for random number generator")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(options["seed"])
        try:
            business = Business.objects.get(name=BUSINESS_NAME)
        except Business.DoesNotExist as exc:
            raise CommandError(f"Business '{BUSINESS_NAME}' does not exist") from exc

        storefront = ensure_storefront(business)
        owner = business.owner
        products = ensure_products(business)
        customers = ensure_customers(business, owner)
        ensure_inventory(business, storefront, products)

        counts = {
            "completed": options["completed"],
            "partial": options["partial"],
            "pending": options["pending"],
            "draft": options["draft"],
        }

        stats = regenerate_sales_dataset(
            business=business,
            storefront=storefront,
            user=owner,
            products=products,
            customers=customers,
            counts=counts,
        )

        total_sales = sum(stats.values())
        self.stdout.write(self.style.SUCCESS(
            f"Generated {total_sales} sales for {BUSINESS_NAME}: "
            f"{stats['COMPLETED']} completed, {stats['PARTIAL']} partial, "
            f"{stats['PENDING']} pending, {stats['DRAFT']} draft."
        ))