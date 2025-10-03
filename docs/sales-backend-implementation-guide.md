# Sales Feature - Backend Implementation Guide

## 📋 Quick Start for Backend Developer

Hi! Welcome to the Sales feature implementation. This README will help you get started quickly with building the backend API based on the comprehensive specifications provided.

## 📚 Documentation Structure

All documentation is in the `/docs` folder with three main documents:

### 1. **sales-feature-specification.md** (2,010 lines) - YOUR MAIN GUIDE
👉 **Start here!** This is your authoritative source for:
- Complete data models with all fields
- 21 API endpoints with request/response examples
- Business logic and validation rules
- Security and permissions
- Error handling
- Performance requirements

### 2. **sales-frontend-implementation-plan.md** (515 lines)
Frontend team's plan - useful to understand:
- How the frontend will consume your API
- Expected response formats
- User workflows from UI perspective
- Component architecture (helps you understand the use cases)

### 3. **sales-documentation-summary.md** (469 lines)
Executive overview - useful for:
- Quick reference
- Understanding business value
- Implementation timeline
- Key features at a glance

## 🎯 Your Implementation Roadmap

### Phase 1: Core Sales & Stock Reservations (Weeks 1-2)
**Goal:** Enable basic cash sales with stock tracking

**Models to create:**
```python
# models.py
class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    receipt_number = models.CharField(max_length=50, unique=True)
    storefront = models.ForeignKey('Storefront', on_delete=models.PROTECT)
    customer = models.ForeignKey('Customer', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    type = models.CharField(max_length=20, choices=SALE_TYPES)
    status = models.CharField(max_length=20, choices=SALE_STATUSES)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Add all other fields from spec

class SaleItem(models.Model):
    # See specification for complete fields
    pass

class StockReservation(models.Model):
    # Critical for preventing overselling
    pass

class AuditLog(models.Model):
    # Log every action
    pass
```

**Endpoints to implement:**
1. `POST /api/sales/` - Create sale (cart)
2. `POST /api/sales/{id}/items/` - Add item
3. `PATCH /api/sales/{id}/items/{item_id}/` - Update item
4. `DELETE /api/sales/{id}/items/{item_id}/` - Remove item
5. `GET /api/storefronts/{id}/stock-products/{product_id}/availability/` - Stock check
6. `POST /api/sales/{id}/complete/` - Checkout

**Key Features:**
- ✅ Stock reservation system (30-minute expiry)
- ✅ Real-time availability calculation
- ✅ Prevent overselling
- ✅ Audit logging for all actions
- ✅ Receipt generation

**Testing Checklist:**
- [ ] Can create sale in DRAFT status
- [ ] Can add items with stock reservation
- [ ] Stock availability updates in real-time
- [ ] Cannot add more than available stock
- [ ] Reservations expire after 30 minutes
- [ ] Checkout commits stock and completes sale
- [ ] Audit log captures all events

### Phase 2: Customer Management & Credit (Weeks 3-4)
**Goal:** Enable wholesale sales with credit management

**Models to create:**
```python
class Customer(models.Model):
    # Credit management fields
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2)
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2)
    available_credit = models.DecimalField(max_digits=10, decimal_places=2)
    credit_terms_days = models.IntegerField(default=30)
    credit_blocked = models.BooleanField(default=False)
    # See spec for all fields

class Payment(models.Model):
    # Payment tracking
    pass

class CreditTransaction(models.Model):
    # Credit history for audit
    pass
```

**Endpoints to implement:**
7. `POST /api/customers/` - Create customer
8. `PATCH /api/customers/{id}/` - Update customer
9. `GET /api/customers/{id}/credit-status/` - Get credit info
10. `POST /api/customers/{id}/payments/` - Record payment
11. `GET /api/customers/{id}/purchases/` - Purchase history

**Business Logic:**
```python
def check_credit_limit(customer, sale_amount):
    """
    Validate customer can make purchase
    
    Rules:
    1. Check customer is not credit_blocked
    2. Check available_credit >= sale_amount
    3. Check no overdue amounts (configurable grace period)
    4. Manager can override with reason
    """
    if customer.credit_blocked:
        raise ValidationError("Customer credit blocked")
    
    if customer.available_credit < sale_amount:
        # Check if manager override present
        if not force:
            raise ValidationError(
                f"Insufficient credit. Available: {customer.available_credit}"
            )
    
    # Check for overdue amounts
    overdue = get_overdue_balance(customer)
    if overdue > 0 and not force:
        raise ValidationError(
            f"Customer has overdue balance: {overdue}"
        )
    
    return True
```

**Testing Checklist:**
- [ ] Can create customer with credit limit
- [ ] Credit limit enforced on sales
- [ ] Outstanding balance updates correctly
- [ ] Can record customer payments
- [ ] Aging report calculates correctly
- [ ] Credit block prevents new sales

### Phase 3: Refunds & Returns (Weeks 5-6)
**Goal:** Handle product returns with warranty checks

**Models to create:**
```python
class Refund(models.Model):
    # See spec for all fields
    pass

class RefundItem(models.Model):
    # Individual items being refunded
    pass
```

**Endpoints to implement:**
12. `POST /api/refunds/` - Request refund
13. `POST /api/refunds/{id}/approve/` - Approve refund
14. `POST /api/refunds/{id}/reject/` - Reject refund
15. `POST /api/refunds/{id}/process/` - Process refund
16. `GET /api/sales/{id}/refund-eligibility/` - Check warranty

**Business Logic:**
```python
def check_warranty_eligibility(sale, items):
    """
    Check if items are within warranty period
    
    Returns:
    {
        'items': [
            {
                'product': 'uuid',
                'is_refundable': True/False,
                'days_since_purchase': 15,
                'warranty_days': 90,
                'reason': 'Within warranty' or 'Warranty expired'
            }
        ]
    }
    """
    results = []
    purchase_date = sale.created_at.date()
    today = datetime.now().date()
    days_since = (today - purchase_date).days
    
    for item in items:
        warranty_days = get_warranty_period(item.product)
        is_refundable = days_since <= warranty_days
        
        results.append({
            'product': item.product.id,
            'product_name': item.product_name,
            'is_refundable': is_refundable,
            'days_since_purchase': days_since,
            'warranty_days': warranty_days,
            'remaining_days': max(0, warranty_days - days_since),
            'reason': 'Within warranty' if is_refundable else 'Warranty expired'
        })
    
    return results

def process_refund(refund):
    """
    Process approved refund
    
    Steps:
    1. Validate refund is APPROVED
    2. Process payment refund
    3. Restock items if applicable
    4. Update original sale
    5. Create audit trail
    6. Update customer credit if applicable
    """
    with transaction.atomic():
        # 1. Validate
        if refund.status != 'APPROVED':
            raise ValidationError("Refund must be approved first")
        
        # 2. Process payment
        if refund.refund_method == 'CASH':
            # Record cash refund
            pass
        elif refund.refund_method == 'CREDIT_NOTE':
            # Add to customer credit
            pass
        elif refund.refund_method == 'ORIGINAL_PAYMENT':
            # Reverse original payment
            pass
        
        # 3. Restock
        for item in refund.refund_items.all():
            if item.restock:
                restock_item(item)
        
        # 4. Update sale
        sale = refund.sale
        sale.amount_due += refund.amount
        if sale.amount_due == sale.total_amount:
            sale.status = 'REFUNDED'
        sale.save()
        
        # 5. Audit
        create_audit_log('refund.processed', refund)
        
        # 6. Update refund status
        refund.status = 'PROCESSED'
        refund.processed_at = datetime.now()
        refund.save()
```

**Testing Checklist:**
- [ ] Can request refund for completed sale
- [ ] Warranty check works correctly
- [ ] Approval workflow functions
- [ ] Refund processing updates stock
- [ ] Customer credit updated correctly
- [ ] Cannot refund more than sold

### Phase 4: Payment Methods (Weeks 7-8)
**Goal:** Support card and mobile money payments

**Endpoints to implement:**
17. `POST /api/payments/card-intent/` - Stripe/Paystack integration
18. `POST /api/payments/mobile-money/` - Mobile money
19. `GET /api/payments/{id}/status/` - Check payment status

**Integration Examples:**

**Stripe Integration:**
```python
import stripe

def create_card_payment_intent(sale):
    """
    Create Stripe payment intent
    """
    intent = stripe.PaymentIntent.create(
        amount=int(sale.total_amount * 100),  # Convert to cents
        currency='ghs',  # or usd
        metadata={
            'sale_id': str(sale.id),
            'receipt_number': sale.receipt_number,
            'storefront': str(sale.storefront.id)
        }
    )
    
    return {
        'client_secret': intent.client_secret,
        'payment_intent_id': intent.id
    }

@webhook_handler
def stripe_webhook(request):
    """
    Handle Stripe webhooks
    """
    event = stripe.Webhook.construct_event(
        request.body,
        request.META['HTTP_STRIPE_SIGNATURE'],
        settings.STRIPE_WEBHOOK_SECRET
    )
    
    if event.type == 'payment_intent.succeeded':
        intent = event.data.object
        sale_id = intent.metadata.sale_id
        
        # Update sale status
        sale = Sale.objects.get(id=sale_id)
        sale.status = 'COMPLETED'
        sale.completed_at = datetime.now()
        sale.save()
        
        # Create payment record
        Payment.objects.create(
            sale=sale,
            amount_paid=Decimal(intent.amount) / 100,
            payment_method='CARD',
            status='SUCCESSFUL',
            transaction_reference=intent.id
        )
```

**Mobile Money Integration:**
```python
def initiate_mobile_money_payment(sale, phone_number, network):
    """
    Initiate mobile money payment
    
    Example for MTN MOMO (Ghana)
    """
    response = requests.post(
        'https://api.mtn.com/collection/v1_0/requesttopay',
        headers={
            'Authorization': f'Bearer {get_momo_token()}',
            'X-Target-Environment': 'production',
            'Ocp-Apim-Subscription-Key': settings.MOMO_SUBSCRIPTION_KEY
        },
        json={
            'amount': str(sale.total_amount),
            'currency': 'GHS',
            'externalId': str(sale.id),
            'payer': {
                'partyIdType': 'MSISDN',
                'partyId': phone_number
            },
            'payerMessage': f'Payment for receipt {sale.receipt_number}',
            'payeeNote': f'Sale payment'
        }
    )
    
    if response.status_code == 202:
        transaction_id = response.headers['X-Reference-Id']
        
        # Create pending payment
        payment = Payment.objects.create(
            sale=sale,
            amount_paid=sale.total_amount,
            payment_method='MOMO',
            status='PENDING',
            transaction_reference=transaction_id,
            phone_number=phone_number
        )
        
        return {
            'transaction_id': transaction_id,
            'status': 'PENDING',
            'message': 'Customer will receive payment prompt'
        }
    else:
        raise PaymentError(response.json())

def check_mobile_money_status(transaction_id):
    """
    Poll mobile money payment status
    """
    response = requests.get(
        f'https://api.mtn.com/collection/v1_0/requesttopay/{transaction_id}',
        headers={
            'Authorization': f'Bearer {get_momo_token()}',
            'X-Target-Environment': 'production',
            'Ocp-Apim-Subscription-Key': settings.MOMO_SUBSCRIPTION_KEY
        }
    )
    
    return response.json()
```

**Testing Checklist:**
- [ ] Card payment creates Stripe intent
- [ ] Webhook updates sale status
- [ ] Mobile money sends prompt
- [ ] Can poll payment status
- [ ] Failed payments handled gracefully
- [ ] Split payments sum correctly

### Phase 5: Reporting (Weeks 9-10)
**Goal:** Provide sales analytics

**Endpoints to implement:**
20. `GET /api/reports/daily-sales/` - Daily summary
21. `GET /api/reports/product-sales/` - Product analytics

**Example Implementation:**
```python
def daily_sales_report(storefront, date):
    """
    Generate daily sales summary
    """
    sales = Sale.objects.filter(
        storefront=storefront,
        created_at__date=date,
        status='COMPLETED'
    )
    
    summary = sales.aggregate(
        total_sales=Sum('total_amount'),
        total_refunds=Sum('refunds__amount'),
        transaction_count=Count('id'),
        avg_transaction=Avg('total_amount'),
        cash_sales=Sum('total_amount', filter=Q(payment_type='CASH')),
        card_sales=Sum('total_amount', filter=Q(payment_type='CARD')),
        credit_sales=Sum('total_amount', filter=Q(payment_type='CREDIT'))
    )
    
    summary['net_sales'] = summary['total_sales'] - summary['total_refunds']
    
    # Top products
    top_products = SaleItem.objects.filter(
        sale__in=sales
    ).values('product__name').annotate(
        units_sold=Sum('quantity'),
        revenue=Sum('total_price')
    ).order_by('-revenue')[:10]
    
    # Hourly breakdown
    by_hour = sales.annotate(
        hour=TruncHour('created_at')
    ).values('hour').annotate(
        sales=Sum('total_amount'),
        transactions=Count('id')
    ).order_by('hour')
    
    return {
        'date': date,
        'storefront': storefront.name,
        'summary': summary,
        'top_products': top_products,
        'by_hour': list(by_hour)
    }
```

## 🔒 Security Checklist

### Authentication & Authorization
- [ ] All endpoints require authentication
- [ ] Implement permission checks using capability system
- [ ] Storefront isolation (users can only access their locations)
- [ ] Manager approval for sensitive operations

### Data Protection
- [ ] Encrypt sensitive customer data (PII)
- [ ] Secure payment processor credentials
- [ ] Hash transaction references
- [ ] Implement rate limiting

### Audit & Compliance
- [ ] Log all sale operations
- [ ] Log all payment transactions
- [ ] Log all refund operations
- [ ] Include IP address and user agent in audit logs
- [ ] Immutable audit logs (no deletion)

## 📊 Database Optimization

### Required Indexes
```sql
-- Sales queries
CREATE INDEX idx_sales_storefront_date ON sales(storefront_id, created_at DESC);
CREATE INDEX idx_sales_customer ON sales(customer_id);
CREATE INDEX idx_sales_status ON sales(status);
CREATE INDEX idx_sales_receipt ON sales(receipt_number);

-- Line items
CREATE INDEX idx_sale_items_product ON sale_items(product_id);
CREATE INDEX idx_sale_items_sale ON sale_items(sale_id);

-- Payments
CREATE INDEX idx_payments_sale ON payments(sale_id);
CREATE INDEX idx_payments_customer ON payments(customer_id);
CREATE INDEX idx_payments_date ON payments(created_at DESC);

-- Reservations
CREATE INDEX idx_reservations_expires ON stock_reservations(expires_at);
CREATE INDEX idx_reservations_status ON stock_reservations(status);
CREATE INDEX idx_reservations_product ON stock_reservations(stock_product_id);

-- Audit logs
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_sale ON audit_logs(sale_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
```

### Query Optimization
```python
# Use select_related for foreign keys
Sale.objects.select_related(
    'customer', 'storefront', 'user'
).prefetch_related(
    'line_items__product',
    'payments',
    'refunds__refund_items'
)

# Use aggregation instead of Python loops
Sale.objects.aggregate(
    total_sales=Sum('total_amount'),
    avg_sale=Avg('total_amount')
)
```

## 🧪 Testing Guidelines

### Unit Tests
```python
class SaleModelTests(TestCase):
    def test_sale_calculation(self):
        """Test sale total calculation"""
        sale = Sale.objects.create(...)
        SaleItem.objects.create(
            sale=sale,
            quantity=2,
            unit_price=10,
            discount_percentage=10
        )
        # Expected: (2 * 10 * 0.9) + tax = 18 + tax
        self.assertEqual(sale.subtotal, Decimal('18.00'))
    
    def test_stock_reservation(self):
        """Test stock is reserved on item add"""
        stock_product = StockProduct.objects.create(quantity=10)
        sale = Sale.objects.create(...)
        
        SaleItem.objects.create(
            sale=sale,
            stock_product=stock_product,
            quantity=5
        )
        
        # Check reservation created
        reservation = StockReservation.objects.get(
            stock_product=stock_product,
            cart_session_id=sale.id
        )
        self.assertEqual(reservation.quantity, 5)
        
        # Check available stock reduced
        availability = get_stock_availability(stock_product)
        self.assertEqual(availability['unreserved'], 5)
```

### Integration Tests
```python
class SaleWorkflowTests(APITestCase):
    def test_complete_sale_flow(self):
        """Test end-to-end sale"""
        # 1. Create sale
        response = self.client.post('/api/sales/', {
            'storefront': self.storefront.id,
            'type': 'RETAIL'
        })
        sale_id = response.data['id']
        
        # 2. Add items
        response = self.client.post(f'/api/sales/{sale_id}/items/', {
            'product': self.product.id,
            'stock_product': self.stock.id,
            'quantity': 2
        })
        self.assertEqual(response.status_code, 201)
        
        # 3. Checkout
        response = self.client.post(f'/api/sales/{sale_id}/complete/', {
            'payment_type': 'CASH',
            'payments': [{
                'payment_method': 'CASH',
                'amount_paid': response.data['total_amount']
            }]
        })
        self.assertEqual(response.status_code, 200)
        
        # 4. Verify stock committed
        self.stock.refresh_from_database()
        self.assertEqual(self.stock.quantity, 8)  # Was 10, sold 2
```

## 🚨 Common Pitfalls to Avoid

### 1. Race Conditions in Stock
**Problem:** Two users add same item simultaneously
**Solution:** Use database transactions and SELECT FOR UPDATE
```python
with transaction.atomic():
    stock = StockProduct.objects.select_for_update().get(id=stock_id)
    if stock.quantity < requested_quantity:
        raise InsufficientStockError()
    stock.quantity -= requested_quantity
    stock.save()
```

### 2. Payment Failures Mid-Transaction
**Problem:** Payment fails after stock committed
**Solution:** Use database transactions
```python
@transaction.atomic
def complete_sale(sale, payments):
    # All or nothing
    for payment in payments:
        process_payment(payment)  # Raises exception on failure
    
    commit_stock(sale)  # Only runs if all payments succeed
    sale.status = 'COMPLETED'
    sale.save()
```

### 3. Floating Point Precision
**Problem:** Money calculations with float lose precision
**Solution:** Always use Decimal
```python
from decimal import Decimal

# Bad
total = 10.1 + 20.2  # = 30.299999999999997

# Good
total = Decimal('10.1') + Decimal('20.2')  # = 30.3
```

### 4. Audit Log Performance
**Problem:** Logging slows down requests
**Solution:** Async logging with Celery
```python
@celery_app.task
def create_audit_log_async(event_type, data):
    AuditLog.objects.create(
        event_type=event_type,
        **data
    )

# In view
create_audit_log_async.delay('sale.completed', {...})
```

## 📞 Support & Questions

**Questions about the specification?**
- Open an issue in GitHub with label `sales-backend-question`
- Tag frontend lead for clarification
- Weekly sync meetings every Monday

**Need clarification on business logic?**
- Refer to `sales-feature-specification.md` first
- Check if similar question answered in spec
- Ask in team chat for quick responses

**Found an issue in the spec?**
- Create GitHub issue with label `spec-clarification`
- Propose solution
- Get approval before implementing

## ✅ Definition of Done

A phase is complete when:
- [ ] All endpoints implemented
- [ ] Unit tests written (>80% coverage)
- [ ] Integration tests pass
- [ ] API documented (OpenAPI/Swagger)
- [ ] Frontend can consume endpoints successfully
- [ ] Performance benchmarks met
- [ ] Security review passed
- [ ] Code reviewed by peer
- [ ] Deployed to staging
- [ ] QA testing completed

## 🎉 Let's Build!

You have everything you need to build an amazing sales API. The specification is comprehensive, the requirements are clear, and the frontend is ready to integrate.

**Remember:**
1. Start with Phase 1 (basic sales)
2. Test thoroughly at each step
3. Communicate early and often
4. Refer to the spec when in doubt
5. Ask questions - no question is too small

**Happy coding! 🚀**
