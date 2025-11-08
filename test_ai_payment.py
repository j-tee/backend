"""
Test AI Credit Purchase with Paystack Integration
Run this script to test the complete payment flow
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
TOKEN = "your-auth-token-here"  # Replace with actual token

# Headers
headers = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

def main():
    print("=" * 60)
    print("AI CREDIT PURCHASE - PAYSTACK INTEGRATION TEST")
    print("=" * 60)
    print()

    # Step 1: Check current balance
    print("Step 1: Checking current credit balance...")
    response = requests.get(f"{BASE_URL}/ai/api/credits/balance/", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Current Balance: {data['balance']} credits")
        print(f"   Expires in: {data.get('days_until_expiry', 'N/A')} days")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        exit(1)

    print()

    # Step 2: Purchase credits
    print("Step 2: Initiating credit purchase...")
    purchase_data = {
        "package": "starter",  # 30 credits for GHS 30
        "payment_method": "mobile_money"
    }

    response = requests.post(
        f"{BASE_URL}/ai/api/credits/purchase/",
        headers=headers,
        json=purchase_data
    )

    if response.status_code == 200:
        data = response.json()
        print("✅ Payment initialized successfully!")
        print()
        print("Paystack Response:")
        print(f"  Authorization URL: {data.get('authorization_url')}")
        print(f"  Reference: {data.get('reference')}")
        print(f"  Amount: GHS {data.get('amount')}")
        print(f"  Credits to add: {data.get('credits_to_add')}")
        print()
        print("=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        print("1. Open this URL in your browser:")
        print(f"   {data.get('authorization_url')}")
        print()
        print("2. Complete payment with test card:")
        print("   Card: 4084084084084081")
        print("   CVV: 408")
        print("   PIN: 0000")
        print("   OTP: 123456")
        print()
        print("3. After payment, Paystack will redirect back")
        print("4. Credits will be automatically added to your account")
        print()
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()
