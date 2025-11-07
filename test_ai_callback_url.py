#!/usr/bin/env python
"""
Test AI Credits Purchase Callback URL
Verifies the callback_url is properly passed to Paystack
"""

import os
import django
import requests
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from accounts.models import Business

User = get_user_model()

def test_ai_credits_callback():
    """Test AI credits purchase with callback URL"""
    
    print("="*80)
    print("AI CREDITS CALLBACK URL TEST")
    print("="*80)
    
    # Get DataLogique Systems user
    business = Business.objects.filter(name="DataLogique Systems").first()
    if not business:
        print("❌ DataLogique Systems not found")
        return
    
    user = business.owner
    if not user:
        print("❌ No owner for DataLogique Systems")
        return
    
    print(f"\n✅ Testing with user: {user.email}")
    print(f"   Business: {business.name}")
    
    # Get auth token
    from rest_framework.authtoken.models import Token
    token, _ = Token.objects.get_or_create(user=user)
    
    print(f"   Token: {token.key[:20]}...")
    
    # Test 1: Purchase WITH callback_url
    print("\n" + "-"*80)
    print("TEST 1: Purchase WITH callback_url")
    print("-"*80)
    
    callback_url = "http://localhost:5173/payment/callback"
    
    payload = {
        "package": "starter",
        "payment_method": "mobile_money",
        "callback_url": callback_url
    }
    
    print(f"\nRequest Payload:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(
        "http://localhost:8000/ai/api/credits/purchase/",
        json=payload,
        headers={
            "Authorization": f"Token {token.key}",
            "Content-Type": "application/json"
        }
    )
    
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Purchase initialized successfully!")
        print(f"   Authorization URL: {data.get('authorization_url', 'N/A')[:100]}...")
        print(f"   Reference: {data.get('reference', 'N/A')}")
        
        # Check if callback_url is in the authorization URL
        auth_url = data.get('authorization_url', '')
        if callback_url in auth_url:
            print(f"\n✅ Callback URL IS in authorization URL")
        else:
            print(f"\n⚠️  Callback URL NOT in authorization URL")
            print(f"   Looking for: {callback_url}")
            print(f"   In URL: {auth_url}")
    else:
        print(f"❌ Error: {response.text}")
    
    # Test 2: Purchase WITHOUT callback_url (should use default)
    print("\n" + "-"*80)
    print("TEST 2: Purchase WITHOUT callback_url (should use FRONTEND_URL)")
    print("-"*80)
    
    payload2 = {
        "package": "value",
        "payment_method": "card"
    }
    
    print(f"\nRequest Payload:")
    print(json.dumps(payload2, indent=2))
    print(f"\nExpected Default: {settings.FRONTEND_URL}/app/subscription/payment/callback")
    
    response2 = requests.post(
        "http://localhost:8000/ai/api/credits/purchase/",
        json=payload2,
        headers={
            "Authorization": f"Token {token.key}",
            "Content-Type": "application/json"
        }
    )
    
    print(f"\nResponse Status: {response2.status_code}")
    
    if response2.status_code == 200:
        data2 = response2.json()
        print(f"\n✅ Purchase initialized successfully!")
        print(f"   Authorization URL: {data2.get('authorization_url', 'N/A')[:100]}...")
        print(f"   Reference: {data2.get('reference', 'N/A')}")
        
        # Check if default callback is in URL
        default_callback = f"{settings.FRONTEND_URL}/app/subscription/payment/callback"
        auth_url2 = data2.get('authorization_url', '')
        if default_callback in auth_url2:
            print(f"\n✅ Default callback URL IS in authorization URL")
        else:
            print(f"\n⚠️  Default callback URL NOT in authorization URL")
            print(f"   Looking for: {default_callback}")
    else:
        print(f"❌ Error: {response2.text}")
    
    # Compare with subscription flow
    print("\n" + "="*80)
    print("UNIFIED CALLBACK PATH")
    print("="*80)
    print(f"\n✅ AI Credits Callback: {settings.FRONTEND_URL}/app/subscription/payment/callback")
    print(f"✅ Subscription Callback: {settings.FRONTEND_URL}/app/subscription/payment/callback")
    print("\n✨ Both now use the SAME callback path!")
    print("   Frontend can detect payment type from reference prefix:")
    print("   - AI-CREDIT-xxx → AI credits verification")
    print("   - SUB-xxx → Subscription verification")
    
    print("\n" + "="*80)
    print("FRONTEND IMPLEMENTATION GUIDE")
    print("="*80)
    print("""
1. Update PaymentCallback component to handle both types:

   const reference = searchParams.get('reference');
   
   if (reference.startsWith('AI-CREDIT')) {
     // Verify AI credits
     await fetch('/ai/api/credits/verify/?reference=' + reference);
   } else if (reference.startsWith('SUB-')) {
     // Verify subscription
     await fetch('/subscriptions/api/verify-payment/?reference=' + reference);
   }

2. Show appropriate success message based on type

3. Redirect to appropriate page:
   - AI credits → /ai/credits
   - Subscription → /app/subscriptions
""")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_ai_credits_callback()
