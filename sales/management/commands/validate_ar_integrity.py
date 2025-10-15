"""
Django management command to validate AR data integrity
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from sales.models import Customer, Sale
from sales.validators import ARIntegrityValidator


class Command(BaseCommand):
    help = 'Validate AR data integrity and detect orphaned balances'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix orphaned balances by recalculating from sales',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each customer',
        )
    
    def handle(self, *args, **options):
        fix_mode = options['fix']
        verbose = options['verbose']
        
        self.stdout.write(self.style.WARNING('='* 70))
        self.stdout.write(self.style.WARNING('AR DATA INTEGRITY VALIDATION'))
        self.stdout.write(self.style.WARNING('='* 70))
        self.stdout.write('')
        
        # Statistics
        total_customers = 0
        customers_with_issues = 0
        total_orphaned_balance = Decimal('0')
        issues_fixed = 0
        
        # Check 1: Customer balances vs actual sales
        self.stdout.write(self.style.HTTP_INFO('CHECK 1: Customer.outstanding_balance vs Sale.amount_due'))
        self.stdout.write('')
        
        for customer in Customer.objects.all():
            total_customers += 1
            
            actual_balance = ARIntegrityValidator.calculate_customer_balance(customer)
            recorded_balance = customer.outstanding_balance
            
            if actual_balance != recorded_balance:
                customers_with_issues += 1
                difference = recorded_balance - actual_balance
                total_orphaned_balance += difference
                
                self.stdout.write(
                    self.style.ERROR(f'  ✗ {customer.name} (ID: {customer.id})')
                )
                self.stdout.write(f'    Recorded balance: ₱{recorded_balance}')
                self.stdout.write(f'    Actual sales AR:  ₱{actual_balance}')
                self.stdout.write(f'    Difference:       ₱{difference} (orphaned)')
                
                if fix_mode:
                    customer.outstanding_balance = actual_balance
                    customer.save(update_fields=['outstanding_balance'])
                    issues_fixed += 1
                    self.stdout.write(self.style.SUCCESS(f'    ✓ FIXED: Set to ₱{actual_balance}'))
                
                self.stdout.write('')
            elif verbose:
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ {customer.name}: ₱{recorded_balance}')
                )
        
        # Check 2: Sales with invalid status/balance combinations
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('CHECK 2: Invalid sale status/balance combinations'))
        self.stdout.write('')
        
        invalid_sales = []
        
        # COMPLETED sales with amount_due > 0
        completed_with_due = Sale.objects.filter(
            status='COMPLETED',
            amount_due__gt=0
        )
        for sale in completed_with_due:
            invalid_sales.append((sale, 'COMPLETED sale has amount_due > 0'))
        
        # CANCELLED sales with amount_due > 0
        cancelled_with_due = Sale.objects.filter(
            status='CANCELLED',
            amount_due__gt=0
        )
        for sale in cancelled_with_due:
            invalid_sales.append((sale, 'CANCELLED sale has amount_due > 0'))
        
        # PENDING sales with amount_paid > 0
        pending_with_paid = Sale.objects.filter(
            status='PENDING',
            amount_paid__gt=0
        )
        for sale in pending_with_paid:
            invalid_sales.append((sale, 'PENDING sale has amount_paid > 0'))
        
        # REFUNDED sales with amount_due > 0
        refunded_with_due = Sale.objects.filter(
            status='REFUNDED',
            amount_due__gt=0
        )
        for sale in refunded_with_due:
            invalid_sales.append((sale, 'REFUNDED sale has amount_due > 0'))
        
        if invalid_sales:
            for sale, issue in invalid_sales:
                self.stdout.write(self.style.ERROR(f'  ✗ Sale {sale.id}'))
                self.stdout.write(f'    Receipt: {sale.receipt_number or "None"}')
                self.stdout.write(f'    Status: {sale.status}')
                self.stdout.write(f'    Total: ₱{sale.total_amount}')
                self.stdout.write(f'    Paid: ₱{sale.amount_paid}')
                self.stdout.write(f'    Due: ₱{sale.amount_due}')
                self.stdout.write(f'    Issue: {issue}')
                
                if fix_mode:
                    if sale.status in ['CANCELLED', 'REFUNDED', 'COMPLETED']:
                        sale.amount_due = Decimal('0')
                        sale.save(update_fields=['amount_due'])
                        issues_fixed += 1
                        self.stdout.write(self.style.SUCCESS('    ✓ FIXED: Set amount_due to ₱0'))
                
                self.stdout.write('')
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ No invalid sales found'))
        
        # Check 3: Sales totals consistency
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('CHECK 3: Sale total = paid + due'))
        self.stdout.write('')
        
        inconsistent_sales = []
        for sale in Sale.objects.all():
            expected_total = sale.amount_paid + sale.amount_due
            if abs(sale.total_amount - expected_total) > Decimal('0.01'):
                inconsistent_sales.append(sale)
                
                self.stdout.write(self.style.ERROR(f'  ✗ Sale {sale.id}'))
                self.stdout.write(f'    total_amount: ₱{sale.total_amount}')
                self.stdout.write(f'    amount_paid:  ₱{sale.amount_paid}')
                self.stdout.write(f'    amount_due:   ₱{sale.amount_due}')
                self.stdout.write(f'    Expected:     ₱{expected_total}')
                self.stdout.write('')
        
        if not inconsistent_sales:
            self.stdout.write(self.style.SUCCESS('  ✓ All sale totals are consistent'))
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('='* 70))
        self.stdout.write(self.style.WARNING('SUMMARY'))
        self.stdout.write(self.style.WARNING('='* 70))
        self.stdout.write('')
        self.stdout.write(f'Total customers checked: {total_customers}')
        self.stdout.write(f'Customers with balance issues: {customers_with_issues}')
        self.stdout.write(f'Total orphaned balance: ₱{total_orphaned_balance}')
        self.stdout.write(f'Invalid sales found: {len(invalid_sales)}')
        self.stdout.write(f'Inconsistent sale totals: {len(inconsistent_sales)}')
        
        if fix_mode:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'✓ Issues fixed: {issues_fixed}'))
        else:
            if customers_with_issues > 0 or invalid_sales:
                self.stdout.write('')
                self.stdout.write(
                    self.style.WARNING('Run with --fix to automatically correct these issues')
                )
        
        self.stdout.write('')
        
        # Exit with error code if issues found
        if customers_with_issues > 0 or invalid_sales or inconsistent_sales:
            if not fix_mode:
                self.stdout.write(
                    self.style.ERROR('⚠ Data integrity issues detected!')
                )
                exit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ All AR data integrity checks passed!')
            )
