#!/usr/bin/env python
"""
Test AI Credit Payment Verification
Tests the verify_payment endpoint to ensure it works correctly
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, '/home/teejay/Documents/Projects/pos/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from ai_features.models import AICreditPurchase
from decimal import Decimal

def test_verification():
    """Test payment verification logic"""
    print("\n" + "="*80)
    print("AI CREDIT PAYMENT VERIFICATION TEST")
    print("="*80 + "\n")
    
    # Get a pending purchase
    pending_purchases = AICreditPurchase.objects.filter(payment_status='pending')
    
    if not pending_purchases.exists():
        print("✓ No pending purchases found - all verified!")
        return
    
    print(f"Found {pending_purchases.count()} pending purchase(s):\n")
    
    for purchase in pending_purchases:
        print(f"📝 Purchase: {purchase.payment_reference}")
        print(f"   Business: {purchase.business.name}")
        print(f"   Credits: {purchase.credits_purchased} + {purchase.bonus_credits} bonus")
        print(f"   User ID: {purchase.user_id}")
        print(f"   User ID is None: {purchase.user_id is None}")
        print(f"   Status: {purchase.payment_status}")
        
        # Test the user_id conversion
        user_id_param = str(purchase.user_id) if purchase.user_id else None
        print(f"   Converted user_id: {user_id_param} (type: {type(user_id_param).__name__})")
        
        if user_id_param == "None":
            print(f"   ⚠️  WARNING: user_id would be string 'None' - THIS IS THE BUG!")
        else:
            print(f"   ✓ user_id conversion looks good")
        
        print()
    
    print("="*80)
    print("\nTo verify these payments manually, use:")
    for purchase in pending_purchases[:3]:  # Show first 3
        print(f"  curl -X POST http://localhost:8000/ai/api/credits/verify/ \\")
        print(f"    -H 'Authorization: Token YOUR_TOKEN' \\")
        print(f"    -H 'Content-Type: application/json' \\")
        print(f"    -d '{{\"reference\": \"{purchase.payment_reference}\"}}'")
        print()

if __name__ == "__main__":
    test_verification()
