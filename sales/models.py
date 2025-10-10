import uuid
from django.db import models, transaction
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from inventory.models import StoreFront, Product, Stock, StockProduct, StoreFrontInventory
from accounts.models import Business


User = get_user_model()


class Customer(models.Model):
    """Customer information and credit management"""
    CUSTOMER_TYPE_CHOICES = [
        ('RETAIL', 'Retail'),
        ('WHOLESALE', 'Wholesale'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='customers', null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='RETAIL')
    
    # Credit management
    credit_limit = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Maximum credit amount allowed"
    )
    outstanding_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Current outstanding balance"
    )
    credit_terms_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(0)],
        help_text="Number of days for credit terms"
    )
    credit_blocked = models.BooleanField(
        default=False,
        help_text="Block customer from making credit purchases"
    )
    
    # Contact information
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_customers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customers'
        ordering = ['name']
        unique_together = ['business', 'phone']  # Prevent duplicate phone numbers per business
        indexes = [
            models.Index(fields=['business', 'name']),
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['outstanding_balance']),
            models.Index(fields=['credit_blocked', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.business.name})"
    
    @property
    def available_credit(self):
        """Calculate available credit"""
        return max(Decimal('0.00'), self.credit_limit - self.outstanding_balance)
    
    def can_purchase(self, amount, force=False):
        """
        Check if customer can make a purchase on credit
        
        Args:
            amount: Purchase amount
            force: Manager override flag
            
        Returns:
            tuple: (can_purchase: bool, message: str)
        """
        if self.credit_blocked and not force:
            return False, "Customer credit is blocked"
        
        if not self.is_active:
            return False, "Customer account is inactive"
        
        if self.available_credit < amount and not force:
            return False, f"Insufficient credit. Available: {self.available_credit}"
        
        # Check for overdue amounts
        overdue = self.get_overdue_balance()
        if overdue > Decimal('0.00') and not force:
            return False, f"Customer has overdue balance: {overdue}"
        
        return True, "OK"
    
    def get_overdue_balance(self):
        """Calculate overdue balance from past-due sales"""
        from django.utils import timezone
        from datetime import timedelta
        
        overdue_sales = self.sales.filter(
            status__in=['PENDING', 'PARTIAL'],
            payment_type='CREDIT',
            created_at__lt=timezone.now() - timedelta(days=self.credit_terms_days)
        )
        
        overdue_total = sum(sale.amount_due for sale in overdue_sales)
        return Decimal(str(overdue_total))
    
    def update_balance(self, amount, transaction_type='ADJUSTMENT'):
        """
        Update customer outstanding balance and create audit trail
        
        Args:
            amount: Amount to add (positive) or subtract (negative)
            transaction_type: Type of transaction
        """
        balance_before = self.outstanding_balance
        self.outstanding_balance += amount
        if self.outstanding_balance < Decimal('0.00'):
            self.outstanding_balance = Decimal('0.00')
        self.save()
        
        # Create credit transaction record
        CreditTransaction.objects.create(
            customer=self,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=self.outstanding_balance
        )


class StockReservation(models.Model):
    """
    Stock reservations for cart functionality
    Prevents overselling by reserving stock when items are added to cart
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMMITTED', 'Committed'),  # Stock has been committed (sale completed)
        ('RELEASED', 'Released'),  # Reservation released (expired or cart abandoned)
        ('CANCELLED', 'Cancelled'),  # Manually cancelled
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_product = models.ForeignKey(
        StockProduct, 
        on_delete=models.CASCADE, 
        related_name='reservations'
    )
    quantity = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    cart_session_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Sale ID or session ID for cart"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True
    )
    
    # Expiry management
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'stock_reservations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock_product', 'status']),
            models.Index(fields=['cart_session_id', 'status']),
            models.Index(fields=['expires_at', 'status']),
        ]
    
    def __str__(self):
        return f"Reservation {self.quantity} of {self.stock_product.product.name} - {self.status}"
    
    @classmethod
    def create_reservation(cls, stock_product, quantity, cart_session_id, expiry_minutes=30):
        """
        Create a stock reservation
        
        Args:
            stock_product: StockProduct instance
            quantity: Quantity to reserve
            cart_session_id: Sale ID or session identifier
            expiry_minutes: Minutes until reservation expires (default 30)
            
        Returns:
            StockReservation instance
            
        Raises:
            ValidationError: If insufficient stock available
        """
        from django.utils import timezone
        from datetime import timedelta
        
        # Check available stock (unreserved quantity)
        available = stock_product.get_available_quantity()

        sale_instance = None
        try:
            sale_instance = Sale.objects.select_related('storefront').get(id=uuid.UUID(str(cart_session_id)))
        except (Sale.DoesNotExist, ValueError, TypeError):
            sale_instance = None

        if sale_instance and sale_instance.storefront_id:
            storefront_inventory = (
                StoreFrontInventory.objects.select_for_update()
                .filter(
                    storefront=sale_instance.storefront,
                    product=stock_product.product,
                )
                .first()
            )

            if storefront_inventory:
                active_reservations = cls.objects.filter(
                    stock_product__product=stock_product.product,
                    status='ACTIVE',
                )

                reservation_sale_ids = []
                for reservation in active_reservations:
                    try:
                        reservation_sale_ids.append(uuid.UUID(str(reservation.cart_session_id)))
                    except (TypeError, ValueError):
                        continue

                storefront_map = {}
                if reservation_sale_ids:
                    storefront_map = {
                        str(sale.id): sale.storefront_id
                        for sale in Sale.objects.filter(id__in=reservation_sale_ids).only('id', 'storefront_id')
                    }

                reserved_for_storefront = Decimal('0.00')
                for reservation in active_reservations:
                    storefront_id = storefront_map.get(reservation.cart_session_id)
                    if storefront_id == sale_instance.storefront_id:
                        reserved_for_storefront += Decimal(reservation.quantity)

                available_storefront = Decimal(str(storefront_inventory.quantity)) - reserved_for_storefront
                if available_storefront < Decimal('0.00'):
                    available_storefront = Decimal('0.00')

                available = available_storefront

        if available < quantity:
            raise ValidationError(
                f"Insufficient stock. Available: {available}, Requested: {quantity}",
                code='insufficient_stock',
                params={
                    'available': str(available),
                    'requested': str(quantity),
                    'stock_product_id': str(stock_product.id),
                    'product_id': str(stock_product.product_id),
                }
            )
        
        # Create reservation
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        reservation = cls.objects.create(
            stock_product=stock_product,
            quantity=quantity,
            cart_session_id=cart_session_id,
            expires_at=expires_at,
            status='ACTIVE'
        )
        
        return reservation
    
    @classmethod
    def release_expired(cls):
        """Release all expired reservations"""
        from django.utils import timezone
        
        expired = cls.objects.filter(
            status='ACTIVE',
            expires_at__lt=timezone.now()
        )
        count = expired.update(
            status='RELEASED',
            released_at=timezone.now()
        )
        return count
    
    def release(self):
        """Release this reservation"""
        if self.status == 'ACTIVE':
            self.status = 'RELEASED'
            self.released_at = timezone.now()
            self.save()
    
    def commit(self):
        """Commit this reservation (stock has been sold)"""
        if self.status == 'ACTIVE':
            self.status = 'COMMITTED'
            self.save()


class Sale(models.Model):
    """Sales transactions - supports cart functionality with DRAFT status"""
    PAYMENT_TYPE_CASH = 'CASH'
    PAYMENT_TYPE_CARD = 'CARD'
    PAYMENT_TYPE_MOBILE = 'MOBILE'
    PAYMENT_TYPE_CREDIT = 'CREDIT'
    PAYMENT_TYPE_MIXED = 'MIXED'

    PAYMENT_TYPE_CHOICES = [
        (PAYMENT_TYPE_CASH, 'Cash'),
        (PAYMENT_TYPE_CARD, 'Card'),
        (PAYMENT_TYPE_MOBILE, 'Mobile Money'),
        (PAYMENT_TYPE_CREDIT, 'Credit'),
        (PAYMENT_TYPE_MIXED, 'Mixed Payment'),
    ]
    
    STATUS_DRAFT = 'DRAFT'
    STATUS_PENDING = 'PENDING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_PARTIAL = 'PARTIAL'
    STATUS_REFUNDED = 'REFUNDED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),  # Cart/incomplete sale
        (STATUS_PENDING, 'Pending'),  # Awaiting payment
        (STATUS_COMPLETED, 'Completed'),  # Fully paid
        (STATUS_PARTIAL, 'Partial'),  # Partially paid
        (STATUS_REFUNDED, 'Refunded'),  # Fully refunded
        (STATUS_CANCELLED, 'Cancelled'),  # Cancelled
    ]
    
    TYPE_RETAIL = 'RETAIL'
    TYPE_WHOLESALE = 'WHOLESALE'

    TYPE_CHOICES = [
        (TYPE_RETAIL, 'Retail'),
        (TYPE_WHOLESALE, 'Wholesale'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='sales', null=True, blank=True)
    storefront = models.ForeignKey(StoreFront, on_delete=models.PROTECT, related_name='sales')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales')  # Cashier/Staff
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    
    # Sale identification
    receipt_number = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    
    # Sale type and status
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_RETAIL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    
    # Amounts
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Sum of line items before discount"
    )
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    amount_paid = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount already paid"
    )
    amount_refunded = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount refunded to the customer"
    )
    amount_due = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Remaining amount to be paid"
    )
    
    # Payment
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default=PAYMENT_TYPE_CASH)
    
    # Manager override for credit limit
    manager_override = models.BooleanField(
        default=False,
        help_text="Manager approved despite credit limit exceeded"
    )
    override_reason = models.TextField(blank=True, null=True)
    override_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='overridden_sales'
    )
    
    # Notes and metadata
    notes = models.TextField(blank=True, null=True)
    
    # Session management for cart
    cart_session_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        db_index=True,
        help_text="Session ID for cart functionality"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'storefront', 'created_at']),
            models.Index(fields=['storefront', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['receipt_number']),
            models.Index(fields=['type', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Sale {self.receipt_number} - {self.status} - {self.total_amount}"
    
    def generate_receipt_number(self):
        """Generate unique receipt number"""
        from django.utils import timezone
        date_str = timezone.now().strftime('%Y%m%d')
        
        # Get count of sales today
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = Sale.objects.filter(
            storefront=self.storefront,
            created_at__gte=today_start
        ).count() + 1
        
        return f"{self.storefront.id}-{date_str}-{count:04d}"
    
    def calculate_totals(self):
        """Calculate all sale totals from line items"""
        from django.db.models import Sum
        
        # Calculate subtotal from line items
        line_items_total = self.sale_items.aggregate(
            subtotal=Sum('total_price')
        )['subtotal'] or Decimal('0.00')
        
        self.subtotal = line_items_total
        
        # Calculate total after discount
        discounted_total = self.subtotal - self.discount_amount
        if discounted_total < Decimal('0.00'):
            discounted_total = Decimal('0.00')
        
        # Add tax
        self.total_amount = discounted_total + self.tax_amount
        
        # Calculate amount due after refunds
        net_paid = self.amount_paid - self.amount_refunded
        if net_paid < Decimal('0.00'):
            net_paid = Decimal('0.00')

        self.amount_due = self.total_amount - net_paid
        if self.amount_due < Decimal('0.00'):
            self.amount_due = Decimal('0.00')
        
        return self.total_amount

    def process_refund(self, *, user, items: list[dict], reason: str, refund_type: str = 'PARTIAL') -> 'Refund':
        """Process a refund for the sale and restock inventory where appropriate."""
        if self.status not in {'COMPLETED', 'PARTIAL', 'PENDING'}:
            raise ValidationError('Only completed or in-progress sales can be refunded.')

        if not items:
            raise ValidationError({'items': 'At least one item is required for a refund.'})

        with transaction.atomic():
            refund = Refund.objects.create(
                sale=self,
                refund_type=refund_type,
                amount=Decimal('0.00'),
                reason=reason,
                status='PROCESSED',
                requested_by=user,
                approved_by=user,
                processed_by=user,
            )

            total_refund = Decimal('0.00')

            for entry in items:
                sale_item: 'SaleItem' = entry['sale_item']
                quantity = int(entry['quantity'])
                if quantity <= 0:
                    raise ValidationError({'quantity': 'Quantity must be greater than zero.'})

                refundable_quantity = sale_item.refundable_quantity
                if quantity > refundable_quantity:
                    raise ValidationError({
                        'quantity': f'Only {refundable_quantity} units available to refund for item {sale_item.id}.'
                    })

                quantity_decimal = Decimal(quantity)
                line_quantity = Decimal(sale_item.quantity)
                if line_quantity <= Decimal('0.00'):
                    raise ValidationError('Sale item quantity is invalid for refund processing.')

                unit_total = (sale_item.total_price / line_quantity).quantize(Decimal('0.01'))
                line_refund = (unit_total * quantity_decimal).quantize(Decimal('0.01'))

                RefundItem.objects.create(
                    refund=refund,
                    sale_item=sale_item,
                    quantity=quantity,
                    amount=line_refund,
                )

                total_refund += line_refund

                # Restock inventory based on where stock was taken from originally
                if self.storefront_id:
                    storefront_inventory, _ = StoreFrontInventory.objects.select_for_update().get_or_create(
                        storefront=self.storefront,
                        product=sale_item.product,
                        defaults={'quantity': 0},
                    )
                    storefront_inventory.quantity += quantity
                    storefront_inventory.save(update_fields=['quantity', 'updated_at'])
                elif sale_item.stock_product_id:
                    stock_product = StockProduct.objects.select_for_update().get(id=sale_item.stock_product_id)
                    stock_product.quantity += quantity
                    stock_product.save(update_fields=['quantity', 'updated_at'])

            refund.amount = total_refund
            refund.save(update_fields=['amount', 'updated_at'])

            self.amount_refunded += total_refund
            self.calculate_totals()

            if self.amount_refunded >= self.total_amount:
                self.status = 'REFUNDED'
            elif self.amount_due > Decimal('0.00'):
                self.status = 'PARTIAL'
            else:
                self.status = 'COMPLETED'

            self.save(update_fields=['amount_refunded', 'amount_due', 'status', 'updated_at'])

            if self.payment_type == 'CREDIT' and self.customer:
                self.customer.update_balance(-total_refund, transaction_type='REFUND')

            AuditLog.log_event(
                event_type='refund.processed',
                user=user,
                sale=self,
                refund=refund,
                customer=self.customer,
                event_data={
                    'refund_id': str(refund.id),
                    'amount': str(total_refund),
                    'refund_type': refund.refund_type,
                },
                description=f'Refund of {total_refund} processed for sale {self.receipt_number}',
            )

            return refund
    
    def cancel_sale(self, *, user, reason: str, restock: bool = True) -> 'Refund':
        """
        Cancel a sale and automatically handle all consequences.
        
        This method:
        1. Validates the sale can be cancelled
        2. Creates a full refund for all items
        3. Restocks inventory to original location (if restock=True)
        4. Updates sale status to CANCELLED
        5. Reverses customer credit balance (if applicable)
        6. Creates comprehensive audit trail
        
        Args:
            user: User performing the cancellation
            reason: Reason for cancellation (required for audit)
            restock: Whether to return items to inventory (default: True)
        
        Returns:
            Refund: The created refund record
        
        Raises:
            ValidationError: If sale cannot be cancelled
        """
        # Validate sale can be cancelled
        if self.status == 'CANCELLED':
            raise ValidationError('Sale is already cancelled.')
        
        if self.status == 'REFUNDED':
            raise ValidationError('Sale has already been fully refunded. Use status update instead.')
        
        # Only allow cancellation of DRAFT, PENDING, COMPLETED, or PARTIAL sales
        if self.status not in {'DRAFT', 'PENDING', 'COMPLETED', 'PARTIAL'}:
            raise ValidationError(f'Cannot cancel sale with status: {self.status}')
        
        with transaction.atomic():
            # Build list of all items to refund
            items_to_refund = []
            for sale_item in self.sale_items.all():
                refundable = sale_item.refundable_quantity
                if refundable > 0:
                    items_to_refund.append({
                        'sale_item': sale_item,
                        'quantity': refundable
                    })
            
            # Process full refund if there are items to refund
            refund = None
            if items_to_refund:
                refund = self.process_refund(
                    user=user,
                    items=items_to_refund,
                    reason=f'Sale Cancellation: {reason}',
                    refund_type='FULL'
                )
            else:
                # No items to refund (already refunded), just update status
                pass
            
            # Update sale status
            old_status = self.status
            self.status = 'CANCELLED'
            self.save(update_fields=['status', 'updated_at'])
            
            # Release any active reservations
            self.release_reservations(delete=True)
            
            # Log the cancellation
            AuditLog.log_event(
                event_type='sale.cancelled',
                user=user,
                sale=self,
                customer=self.customer,
                event_data={
                    'reason': reason,
                    'previous_status': old_status,
                    'refund_id': str(refund.id) if refund else None,
                    'refund_amount': str(refund.amount) if refund else '0.00',
                    'restock': restock,
                    'items_count': len(items_to_refund),
                },
                description=f'Sale {self.receipt_number} cancelled by {user.name}: {reason}',
            )
            
            return refund
    
    def commit_stock(self):
        """
        Commit stock quantities for all sale items
        Called when sale is completed
        """
        with transaction.atomic():
            for item in self.sale_items.select_related('product', 'stock_product').all():
                quantity_decimal = Decimal(item.quantity)
                if quantity_decimal != quantity_decimal.to_integral_value():
                    raise ValidationError(
                        f"Fractional quantity {quantity_decimal} for {item.product.name} is not supported for stock deduction."
                    )
                quantity_required = int(quantity_decimal)

                if item.stock_product and not self.storefront_id:
                    # Reduce stock quantity at the warehouse level
                    stock_product = StockProduct.objects.select_for_update().get(id=item.stock_product.id)
                    if stock_product.quantity < quantity_required:
                        raise ValidationError(
                            f"Insufficient stock for {item.product.name}. "
                            f"Available: {stock_product.quantity}, Required: {quantity_required}"
                        )
                    stock_product.quantity = stock_product.quantity - quantity_required
                    if stock_product.quantity < 0:
                        raise ValidationError(f"Stock level for {item.product.name} would become negative.")
                    stock_product.save(update_fields=['quantity', 'updated_at'])

                if self.storefront_id:
                    storefront_inventory, _ = StoreFrontInventory.objects.select_for_update().get_or_create(
                        storefront=self.storefront,
                        product=item.product,
                        defaults={'quantity': 0}
                    )

                    current_qty = int(storefront_inventory.quantity)
                    if current_qty < quantity_required:
                        raise ValidationError(
                            f"Insufficient storefront stock for {item.product.name}. "
                            f"Available: {current_qty}, Required: {quantity_required}"
                        )

                    new_qty = current_qty - quantity_required
                    if new_qty < 0:
                        raise ValidationError(f"Storefront stock level for {item.product.name} would become negative.")

                    storefront_inventory.quantity = new_qty
                    storefront_inventory.save(update_fields=['quantity', 'updated_at'])
    
    def release_reservations(self, *, delete: bool = False):
        """Release all stock reservations for this sale.

        Args:
            delete: When True, delete all reservations linked to this sale
                after marking any active holds as released.
        """
        reservations = StockReservation.objects.filter(cart_session_id=str(self.id))

        # Mark any outstanding holds as released before cleanup
        reservations.filter(status='ACTIVE').update(
            status='RELEASED',
            released_at=timezone.now()
        )

        if delete:
            reservations.delete()
    
    def complete_sale(self):
        """
        Complete the sale - commit stock and update status
        Should be called in a transaction
        """
        with transaction.atomic():
            # Validate sale can be completed
            if self.status != 'DRAFT':
                raise ValidationError(f"Cannot complete sale with status {self.status}")
            
            if not self.sale_items.exists():
                raise ValidationError("Cannot complete sale without items")
            
            # Generate receipt number if not set
            if not self.receipt_number:
                self.receipt_number = self.generate_receipt_number()
            
            # Commit stock
            self.commit_stock()
            
            # Release reservations and remove draft/session artifacts
            self.release_reservations(delete=True)
            self.cart_session_id = None
            
            # Update status based on payment
            if self.amount_due == Decimal('0.00'):
                self.status = 'COMPLETED'
            elif self.amount_paid > Decimal('0.00'):
                self.status = 'PARTIAL'
            else:
                self.status = 'PENDING'
            
            self.completed_at = timezone.now()
            self.save()
            
            # Update customer credit if applicable
            if self.payment_type == 'CREDIT' and self.customer:
                self.customer.update_balance(
                    self.amount_due,
                    transaction_type='CREDIT_SALE'
                )
    
    def save(self, *args, **kwargs):
        """Override save - receipt number only generated on completion"""
        super().save(*args, **kwargs)


class SaleItem(models.Model):
    """Individual items in a sale"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='sale_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    stock = models.ForeignKey(Stock, on_delete=models.SET_NULL, null=True, blank=True, related_name='sale_items')
    stock_product = models.ForeignKey(StockProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='sale_items')
    
    # Quantities and pricing
    quantity = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    unit_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Tax
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Calculated totals
    total_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Product snapshot (for historical reference)
    product_name = models.CharField(max_length=255, blank=True)
    product_sku = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sales_items'
        indexes = [
            models.Index(fields=['sale', 'product']),
            models.Index(fields=['product', 'stock']),
            models.Index(fields=['product', 'stock_product']),
        ]
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity} - {self.total_price}"
    
    @property
    def base_amount(self):
        """Amount before tax (unit_price * quantity - discount)"""
        line_total = self.unit_price * self.quantity
        return line_total - self.discount_amount
    
    @property
    def gross_amount(self):
        """Total amount including tax"""
        return self.base_amount + self.tax_amount
    
    @property
    def unit_cost(self):
        """Get the cost per unit for this sale item"""
        if self.stock_product:
            # Use the specific StockProduct entry
            return self.stock_product.landed_unit_cost
        elif self.stock:
            # Fallback: Get the StockProduct for this specific stock and product
            try:
                stock_product = StockProduct.objects.get(stock=self.stock, product=self.product)
                return stock_product.landed_unit_cost
            except StockProduct.DoesNotExist:
                pass
        # Final fallback to product's latest cost
        return self.product.get_latest_cost() if hasattr(self.product, 'get_latest_cost') else Decimal('0.00')
    
    @property
    def profit_amount(self):
        """Calculate profit amount per unit (selling price - cost)"""
        return self.unit_price - self.unit_cost
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage ((selling_price - cost) / selling_price * 100)"""
        if self.unit_price <= Decimal('0.00'):
            return Decimal('0.00')
        return ((self.unit_price - self.unit_cost) / self.unit_price * Decimal('100')).quantize(Decimal('0.01'))
    
    @property
    def total_profit_amount(self):
        """Calculate total profit amount for this line item"""
        return self.profit_amount * self.quantity
    
    def calculate_totals(self):
        """Calculate all amounts for this line item"""
        # Calculate discount from percentage if set
        if self.discount_percentage > Decimal('0.00') and self.discount_amount == Decimal('0.00'):
            line_total = self.unit_price * self.quantity
            self.discount_amount = (line_total * self.discount_percentage / Decimal('100.00')).quantize(Decimal('0.01'))
        
        # Calculate base amount
        base = self.base_amount
        if base < Decimal('0.00'):
            base = Decimal('0.00')
        
        # Calculate tax
        if self.tax_rate > Decimal('0.00'):
            self.tax_amount = (base * self.tax_rate / Decimal('100.00')).quantize(Decimal('0.01'))
        
        # Calculate total
        self.total_price = (base + self.tax_amount).quantize(Decimal('0.01'))
        
        return self.total_price
    
    def save(self, *args, **kwargs):
        """Calculate totals and snapshot product info before saving"""
        # Snapshot product info
        if not self.product_name:
            self.product_name = self.product.name
        if not self.product_sku:
            self.product_sku = self.product.sku
        
        # Calculate totals
        self.calculate_totals()
        
        super().save(*args, **kwargs)

    @property
    def refunded_quantity(self) -> int:
        """Return the total quantity already refunded for this sale item."""
        total = self.refund_items.aggregate(total=Sum('quantity'))['total'] or 0
        return int(total)

    @property
    def refundable_quantity(self) -> int:
        """Maximum quantity still available to refund."""
        original_quantity = int(Decimal(self.quantity))
        remaining = original_quantity - self.refunded_quantity
        return remaining if remaining > 0 else 0


class Payment(models.Model):
    """Payments made against sales or customer accounts"""
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('MOMO', 'Mobile Money'),
        ('CARD', 'Card'),
        ('PAYSTACK', 'Paystack'),
        ('STRIPE', 'Stripe'),
        ('BANK_TRANSFER', 'Bank Transfer'),
    ]
    
    STATUS_CHOICES = [
        ('SUCCESSFUL', 'Successful'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESSFUL')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_payments')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['sale', 'status']),
            models.Index(fields=['customer', 'payment_date']),
            models.Index(fields=['payment_method', 'status']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"Payment {self.amount_paid} - {self.payment_method} - {self.customer.name}"


class Refund(models.Model):
    """Refunds for returned items"""
    REFUND_TYPE_CHOICES = [
        ('FULL', 'Full Refund'),
        ('PARTIAL', 'Partial Refund'),
        ('EXCHANGE', 'Exchange'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('PROCESSED', 'Processed'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='refunds')
    refund_type = models.CharField(max_length=20, choices=REFUND_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_refunds')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_refunds')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sale', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Refund {self.amount} for Sale {self.sale.receipt_number}"


class RefundItem(models.Model):
    """Individual items being refunded"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    refund = models.ForeignKey(Refund, on_delete=models.CASCADE, related_name='refund_items')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name='refund_items')
    quantity = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'refund_items'
        indexes = [
            models.Index(fields=['refund', 'sale_item']),
        ]
    
    def __str__(self):
        return f"Refund {self.quantity} x {self.sale_item.product.name}"


class CreditTransaction(models.Model):
    """Credit transactions for customer credit management"""
    TRANSACTION_TYPE_CHOICES = [
        ('CREDIT_SALE', 'Credit Sale'),
        ('PAYMENT', 'Payment'),
        ('ADJUSTMENT', 'Adjustment'),
        ('REFUND', 'Refund'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='credit_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    reference_id = models.UUIDField(null=True, blank=True)  # Sale ID, Payment ID, etc.
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='credit_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'credit_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.customer.name} - {self.transaction_type} - {self.amount}"


class AuditLog(models.Model):
    """
    Audit log for tracking all sales-related actions
    Immutable - records cannot be deleted or modified
    """
    EVENT_TYPES = [
        ('sale.created', 'Sale Created'),
        ('sale.updated', 'Sale Updated'),
        ('sale.completed', 'Sale Completed'),
        ('sale.cancelled', 'Sale Cancelled'),
        ('sale_item.added', 'Sale Item Added'),
        ('sale_item.updated', 'Sale Item Updated'),
        ('sale_item.removed', 'Sale Item Removed'),
        ('payment.created', 'Payment Created'),
        ('payment.updated', 'Payment Updated'),
        ('refund.requested', 'Refund Requested'),
        ('refund.approved', 'Refund Approved'),
        ('refund.rejected', 'Refund Rejected'),
        ('refund.processed', 'Refund Processed'),
        ('stock.reserved', 'Stock Reserved'),
        ('stock.committed', 'Stock Committed'),
        ('stock.released', 'Stock Released'),
        ('customer.created', 'Customer Created'),
        ('customer.updated', 'Customer Updated'),
        ('credit.adjusted', 'Credit Adjusted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    
    # Related objects
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    refund = models.ForeignKey(Refund, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    
    # User and context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales_audit_logs')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Event data
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON data about the event"
    )
    description = models.TextField(blank=True, null=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'sales_audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['sale', 'timestamp']),
            models.Index(fields=['customer', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        # Make audit logs immutable
        permissions = [
            ('view_sales_audit', 'Can view sales audit logs'),
        ]
    
    def __str__(self):
        return f"{self.event_type} at {self.timestamp} by {self.user}"
    
    @classmethod
    def log_event(cls, event_type, user=None, sale=None, sale_item=None, customer=None, 
                  payment=None, refund=None, event_data=None, description=None,
                  ip_address=None, user_agent=None):
        """
        Create an audit log entry
        
        Args:
            event_type: Type of event (from EVENT_TYPES)
            user: User who performed the action
            sale: Related Sale object
            sale_item: Related SaleItem object
            customer: Related Customer object
            payment: Related Payment object
            refund: Related Refund object
            event_data: Additional data as dict
            description: Human-readable description
            ip_address: IP address of the request
            user_agent: User agent string
            
        Returns:
            AuditLog instance
        """
        return cls.objects.create(
            event_type=event_type,
            user=user,
            sale=sale,
            sale_item=sale_item,
            customer=customer,
            payment=payment,
            refund=refund,
            event_data=event_data or {},
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def save(self, *args, **kwargs):
        """Override save to make audit logs immutable after creation"""
        # Check if this is an update (record exists in DB)
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit logs cannot be modified")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of audit logs"""
        raise ValidationError("Audit logs cannot be deleted")
