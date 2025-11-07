#!/usr/bin/env python
"""
Manual AI Credit Payment Processor

This script manually processes pending AI credit payments that failed verification.
It bypasses the verify endpoint and directly adds credits to the database.

Usage:
    python manual_credit_processor.py AI-CREDIT-1762542056443-08ed01c0
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from ai_features.models import AICreditPurchase, BusinessAICredits
from ai_features.services.paystack import PaystackService
from ai_features.services.billing import AIBillingService
from decimal import Decimal
from django.utils import timezone

def process_payment(reference):
    """Manually process a payment"""
    print(f"\n{'='*60}")
    print(f"MANUAL CREDIT PROCESSOR")
    print(f"Reference: {reference}")
    print(f"{'='*60}\n")
    
    # Step 1: Get purchase record
    print("Step 1: Fetching purchase record...")
    try:
        purchase = AICreditPurchase.objects.get(payment_reference=reference)
        print(f"✅ Found purchase record")
        print(f"   Business ID: {purchase.business_id}")
        print(f"   User ID: {purchase.user_id}")
        print(f"   Amount: GHS {purchase.amount_paid}")
        print(f"   Credits: {purchase.credits_purchased}")
        print(f"   Bonus: {purchase.bonus_credits}")
        print(f"   Status: {purchase.payment_status}")
    except AICreditPurchase.DoesNotExist:
        print(f"❌ ERROR: No purchase record found for {reference}")
        return False
    
    # Step 2: Check if already processed
    if purchase.payment_status == 'completed':
        print(f"\n⚠️  Payment already processed at {purchase.completed_at}")
        balance = AIBillingService.get_credit_balance(str(purchase.business_id))
        print(f"   Current balance: {balance} credits")
        return True
    
    # Step 3: Verify with Paystack
    print("\nStep 2: Verifying with Paystack...")
    try:
        payment_data = PaystackService.verify_transaction(reference)
        print(f"✅ Paystack verification successful")
        print(f"   Status: {payment_data['status']}")
        print(f"   Amount: GHS {Decimal(str(payment_data['amount'])) / Decimal('100')}")
        
        if payment_data['status'] != 'success':
            print(f"\n❌ ERROR: Payment status is '{payment_data['status']}', not 'success'")
            print("   Payment was not completed successfully on Paystack")
            return False
    except Exception as e:
        print(f"❌ ERROR verifying with Paystack: {e}")
        return False
    
    # Step 4: Add credits
    print("\nStep 3: Adding credits to account...")
    try:
        amount_paid_ghs = Decimal(str(payment_data['amount'])) / Decimal('100')
        
        total_credits = purchase.credits_purchased + purchase.bonus_credits
        print(f"   Adding {total_credits} credits ({purchase.credits_purchased} + {purchase.bonus_credits} bonus)")
        
        result = AIBillingService.purchase_credits(
            business_id=str(purchase.business_id),
            amount_paid=amount_paid_ghs,
            credits_purchased=purchase.credits_purchased,
            payment_reference=reference,
            payment_method=purchase.payment_method,
            user_id=str(purchase.user_id) if purchase.user_id else None,
            bonus_credits=purchase.bonus_credits
        )
        
        print(f"✅ Credits added successfully!")
        print(f"   Credits added: {result['credits_added']}")
        print(f"   New balance: {result['new_balance']}")
        print(f"   Expires at: {result['expires_at']}")
        
    except Exception as e:
        print(f"❌ ERROR adding credits: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    # Step 5: Update purchase record
    print("\nStep 4: Updating purchase status...")
    try:
        purchase.payment_status = 'completed'
        purchase.completed_at = timezone.now()
        purchase.save()
        print(f"✅ Purchase status updated to 'completed'")
    except Exception as e:
        print(f"❌ ERROR updating purchase: {e}")
        return False
    
    print(f"\n{'='*60}")
    print("✅ SUCCESS! Payment processed manually")
    print(f"{'='*60}\n")
    return True

def list_pending_payments():
    """List all pending payments"""
    print(f"\n{'='*60}")
    print("PENDING AI CREDIT PAYMENTS")
    print(f"{'='*60}\n")
    
    pending = AICreditPurchase.objects.filter(payment_status='pending').order_by('-purchased_at')
    
    if not pending.exists():
        print("No pending payments found")
        return
    
    print(f"Found {pending.count()} pending payment(s):\n")
    
    for i, purchase in enumerate(pending, 1):
        print(f"{i}. {purchase.payment_reference}")
        print(f"   Created: {purchase.purchased_at}")
        print(f"   Amount: GHS {purchase.amount_paid}")
        print(f"   Credits: {purchase.credits_purchased + purchase.bonus_credits}")
        print()

def show_usage():
    print("""
Manual AI Credit Payment Processor
===================================

Usage:
    python manual_credit_processor.py <reference>
    python manual_credit_processor.py --list

Commands:
    <reference>   Process a specific payment reference
    --list        List all pending payments

Examples:
    # Process specific payment
    python manual_credit_processor.py AI-CREDIT-1762542056443-08ed01c0
    
    # List pending payments
    python manual_credit_processor.py --list
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(1)
    
    if sys.argv[1] == '--list':
        list_pending_payments()
    else:
        reference = sys.argv[1]
        success = process_payment(reference)
        sys.exit(0 if success else 1)
