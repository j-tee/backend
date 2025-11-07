#!/usr/bin/env python
"""
Debug AI Credit Payment Issue

This script checks:
1. If purchase record exists in database
2. Paystack verification status
3. Why verification endpoint is failing with 500 error

Usage:
    python debug_ai_credit_payment.py AI-CREDIT-1762542056443-08ed01c0
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from ai_features.models import AICreditPurchase
from ai_features.services.paystack import PaystackService
from decimal import Decimal

def debug_payment(reference):
    """Debug a specific payment reference"""
    print(f"\n{'='*60}")
    print(f"DEBUGGING AI CREDIT PAYMENT: {reference}")
    print(f"{'='*60}\n")
    
    # Step 1: Check if purchase record exists
    print("STEP 1: Checking database for purchase record...")
    try:
        purchase = AICreditPurchase.objects.get(payment_reference=reference)
        print("✅ Purchase record found in database")
        print(f"   Business ID: {purchase.business_id}")
        print(f"   User ID: {purchase.user_id}")
        print(f"   Amount Paid: GHS {purchase.amount_paid}")
        print(f"   Credits Purchased: {purchase.credits_purchased}")
        print(f"   Bonus Credits: {purchase.bonus_credits}")
        print(f"   Payment Method: {purchase.payment_method}")
        print(f"   Payment Status: {purchase.payment_status}")
        print(f"   Created At: {purchase.purchased_at}")
        if purchase.completed_at:
            print(f"   Completed At: {purchase.completed_at}")
    except AICreditPurchase.DoesNotExist:
        print("❌ ERROR: Purchase record not found in database!")
        print("\n   This means the purchase was not created when user clicked 'Purchase Credits'")
        print("   Possible causes:")
        print("   1. User didn't complete the purchase flow")
        print("   2. Database error during purchase creation")
        print("   3. Wrong reference (check the reference in the URL)")
        return
    except Exception as e:
        print(f"❌ ERROR querying database: {e}")
        return
    
    # Step 2: Check Paystack verification
    print("\nSTEP 2: Verifying payment with Paystack...")
    try:
        payment_data = PaystackService.verify_transaction(reference)
        print("✅ Paystack verification successful")
        print(f"   Status: {payment_data.get('status')}")
        print(f"   Amount (pesewas): {payment_data.get('amount')}")
        print(f"   Amount (GHS): {Decimal(str(payment_data.get('amount', 0))) / Decimal('100')}")
        print(f"   Currency: {payment_data.get('currency')}")
        print(f"   Paid At: {payment_data.get('paid_at')}")
        print(f"   Channel: {payment_data.get('channel')}")
        
        if payment_data.get('status') != 'success':
            print(f"\n❌ WARNING: Payment status is '{payment_data.get('status')}', not 'success'")
            print("   This means payment was not completed successfully")
            return
            
    except Exception as e:
        print(f"❌ ERROR verifying with Paystack: {e}")
        print("\n   Possible causes:")
        print("   1. Invalid Paystack API keys")
        print("   2. Network error")
        print("   3. Reference doesn't exist in Paystack")
        return
    
    # Step 3: Simulate the verification endpoint logic
    print("\nSTEP 3: Simulating verification endpoint logic...")
    try:
        # Check if already processed
        if purchase.payment_status == 'completed':
            print("⚠️  Payment already processed!")
            print(f"   Credits were added at: {purchase.completed_at}")
            
            # Check current balance
            from ai_features.services.billing import AIBillingService
            balance = AIBillingService.get_credit_balance(str(purchase.business_id))
            print(f"   Current balance: {balance} credits")
            return
        
        # Convert amount
        amount_paid_ghs = Decimal(str(payment_data['amount'])) / Decimal('100')
        print(f"✅ Amount conversion: {amount_paid_ghs} GHS")
        
        # Prepare parameters for purchase_credits
        print("\n✅ Preparing to add credits...")
        print(f"   Business ID: {purchase.business_id}")
        print(f"   User ID: {purchase.user_id}")
        print(f"   Credits to add: {purchase.credits_purchased + purchase.bonus_credits}")
        
        # This is where the error might be happening
        user_id_param = str(purchase.user_id) if purchase.user_id else None
        print(f"   User ID param: {user_id_param} (type: {type(user_id_param)})")
        
        if user_id_param == "None":
            print("\n❌ BUG FOUND: user_id is string 'None' instead of None!")
            print("   This will cause UUID validation error")
            print("   Fix: Change line 400 in ai_features/views.py")
            print("   From: user_id=str(purchase.user_id)")
            print("   To:   user_id=str(purchase.user_id) if purchase.user_id else None")
            return
        
        # Try to add credits
        from ai_features.services.billing import AIBillingService
        result = AIBillingService.purchase_credits(
            business_id=str(purchase.business_id),
            amount_paid=amount_paid_ghs,
            credits_purchased=purchase.credits_purchased,
            payment_reference=reference,
            payment_method=purchase.payment_method,
            user_id=user_id_param,
            bonus_credits=purchase.bonus_credits
        )
        
        print("✅ Credits added successfully!")
        print(f"   Credits added: {result['credits_added']}")
        print(f"   New balance: {result['new_balance']}")
        
        # Update purchase status
        purchase.payment_status = 'completed'
        from django.utils import timezone
        purchase.completed_at = timezone.now()
        purchase.save()
        
        print("✅ Purchase status updated to 'completed'")
        print(f"\n{'='*60}")
        print("SUCCESS! Payment verified and credits added!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ ERROR during credit addition: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        print("\n   Full traceback:")
        print(traceback.format_exc())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_ai_credit_payment.py <reference>")
        print("\nExample:")
        print("  python debug_ai_credit_payment.py AI-CREDIT-1762542056443-08ed01c0")
        sys.exit(1)
    
    reference = sys.argv[1]
    debug_payment(reference)
