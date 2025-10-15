"""
Data integrity validators for the sales module
Ensures AR balances are always tied to actual sales
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum


class ARIntegrityValidator:
    """
    Validates that Customer.outstanding_balance matches actual sales
    Prevents orphaned AR data
    """
    
    @staticmethod
    def validate_customer_balance(customer):
        """
        Validate that customer's outstanding_balance matches actual sales
        
        Args:
            customer: Customer instance
            
        Raises:
            ValidationError if balance doesn't match actual sales
        """
        from sales.models import Sale
        
        # Calculate actual AR from sales
        actual_ar = Sale.objects.filter(
            customer=customer,
            status__in=['PENDING', 'PARTIAL']
        ).aggregate(
            total=Sum('amount_due')
        )['total'] or Decimal('0')
        
        if customer.outstanding_balance != actual_ar:
            raise ValidationError(
                f"Customer balance mismatch: "
                f"outstanding_balance=₱{customer.outstanding_balance}, "
                f"actual sales AR=₱{actual_ar}. "
                f"Outstanding balance must match sum of PENDING/PARTIAL sales."
            )
    
    @staticmethod
    def calculate_customer_balance(customer):
        """
        Calculate customer's actual outstanding balance from sales
        
        Args:
            customer: Customer instance
            
        Returns:
            Decimal: Actual outstanding balance
        """
        from sales.models import Sale
        
        return Sale.objects.filter(
            customer=customer,
            status__in=['PENDING', 'PARTIAL']
        ).aggregate(
            total=Sum('amount_due')
        )['total'] or Decimal('0')
    
    @staticmethod
    def validate_sale_balance_consistency(sale):
        """
        Validate that sale balance fields are consistent
        
        Args:
            sale: Sale instance
            
        Raises:
            ValidationError if balance fields are inconsistent
        """
        # Check: total_amount = amount_paid + amount_due
        expected_total = sale.amount_paid + sale.amount_due
        if abs(sale.total_amount - expected_total) > Decimal('0.01'):  # Allow 1 cent rounding
            raise ValidationError(
                f"Sale balance inconsistent: "
                f"total_amount=₱{sale.total_amount}, "
                f"amount_paid=₱{sale.amount_paid}, "
                f"amount_due=₱{sale.amount_due}. "
                f"Expected: total_amount = amount_paid + amount_due"
            )
        
        # Check: COMPLETED sales should have amount_due = 0
        if sale.status == 'COMPLETED' and sale.amount_due > Decimal('0'):
            raise ValidationError(
                f"COMPLETED sale cannot have amount_due > 0. "
                f"Sale {sale.id} has amount_due=₱{sale.amount_due}"
            )
        
        # Check: CANCELLED/REFUNDED sales should have amount_due = 0
        if sale.status in ['CANCELLED', 'REFUNDED'] and sale.amount_due > Decimal('0'):
            raise ValidationError(
                f"{sale.status} sale cannot have amount_due > 0. "
                f"Sale {sale.id} has amount_due=₱{sale.amount_due}"
            )
        
        # Check: PENDING sales should have amount_paid = 0
        if sale.status == 'PENDING' and sale.amount_paid > Decimal('0'):
            raise ValidationError(
                f"PENDING sale cannot have amount_paid > 0. "
                f"Sale {sale.id} has amount_paid=₱{sale.amount_paid}"
            )
        
        # Check: PARTIAL sales should have both amount_paid > 0 and amount_due > 0
        if sale.status == 'PARTIAL':
            if sale.amount_paid <= Decimal('0'):
                raise ValidationError(
                    f"PARTIAL sale must have amount_paid > 0. "
                    f"Sale {sale.id} has amount_paid=₱{sale.amount_paid}"
                )
            if sale.amount_due <= Decimal('0'):
                raise ValidationError(
                    f"PARTIAL sale must have amount_due > 0. "
                    f"Sale {sale.id} has amount_due=₱{sale.amount_due}"
                )
    
    @staticmethod
    def validate_ar_has_sale(customer, amount_due):
        """
        Validate that AR amount is backed by actual sale records
        
        Args:
            customer: Customer instance
            amount_due: Amount being added to AR
            
        Raises:
            ValidationError if AR would exist without corresponding sales
        """
        if amount_due <= Decimal('0'):
            return
        
        from sales.models import Sale
        
        # Check that there's at least one sale that justifies this AR
        has_sale = Sale.objects.filter(
            customer=customer,
            status__in=['PENDING', 'PARTIAL'],
            amount_due__gt=0
        ).exists()
        
        if not has_sale:
            raise ValidationError(
                f"Cannot create AR for customer {customer.name} "
                f"without a corresponding PENDING or PARTIAL sale. "
                f"AR must be tied to actual sales."
            )
    
    @staticmethod
    def sync_customer_balance(customer, save=True):
        """
        Synchronize customer balance with actual sales
        
        Args:
            customer: Customer instance
            save: Whether to save the customer after sync
            
        Returns:
            tuple: (old_balance, new_balance, difference)
        """
        old_balance = customer.outstanding_balance
        new_balance = ARIntegrityValidator.calculate_customer_balance(customer)
        difference = new_balance - old_balance
        
        if save and old_balance != new_balance:
            customer.outstanding_balance = new_balance
            customer.save(update_fields=['outstanding_balance'])
        
        return (old_balance, new_balance, difference)
