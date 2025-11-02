#!/usr/bin/env python
"""
Test script for Subscription Payment API endpoints
Tests the complete payment flow: create → initialize → verify
"""

import os
import sys
import django
import json
from decimal import Decimal

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import force_authenticate
from subscriptions.models import (
    SubscriptionPlan, Subscription, SubscriptionPayment,
    SubscriptionPricingTier, TaxConfiguration, ServiceCharge
)
from subscriptions.views import SubscriptionViewSet
from accounts.models import Business, BusinessMembership
from inventory.models import StoreFront

User = get_user_model()

def setup_test_data():
    """Create test data for payment flow"""
    print("Setting up test data...")
    
    # Create test user
    user = User.objects.filter(email='test_payment@example.com').first()
    if not user:
        user = User.objects.create_user(
            email='test_payment@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    print(f"✓ User: {user.email}")
    
    # Create test business
    business = Business.objects.filter(business_name='Test Payment Business').first()
    if not business:
        business = Business.objects.create(
            business_name='Test Payment Business',
            business_type='RETAIL',
            subscription_status='INACTIVE'
        )
    print(f"✓ Business: {business.business_name}")
    
    # Add user as business member
    membership = BusinessMembership.objects.filter(
        user=user,
        business=business
    ).first()
    if not membership:
        membership = BusinessMembership.objects.create(
            user=user,
            business=business,
            role='OWNER'
        )
    print(f"✓ Business Membership: {membership.role}")
    
    # Create storefronts
    storefront_count = 3
    for i in range(storefront_count):
        storefront, created = StoreFront.objects.get_or_create(
            name=f'Test Storefront {i+1}',
            defaults={'business': business}
        )
        BusinessMembership.objects.get_or_create(
            user=user,
            business=business,
            storefront=storefront,
            defaults={'role': 'OWNER'}
        )
    print(f"✓ Storefronts: {storefront_count}")
    
    # Create subscription plan
    plan = SubscriptionPlan.objects.filter(name='Test Professional Plan').first()
    if not plan:
        plan = SubscriptionPlan.objects.create(
            name='Test Professional Plan',
            description='Professional plan for testing',
            price=Decimal('299.99'),
            currency='GHS',
            billing_cycle='MONTHLY',
            max_users=10,
            max_storefronts=5,
            max_products=1000,
            is_active=True
        )
    print(f"✓ Plan: {plan.name} ({plan.price} {plan.currency})")
    
    # Create pricing tier
    tier = SubscriptionPricingTier.objects.filter(
        name='Test Tier 1-5 Storefronts'
    ).first()
    if not tier:
        tier = SubscriptionPricingTier.objects.create(
            name='Test Tier 1-5 Storefronts',
            min_storefronts=1,
            max_storefronts=5,
            base_price=Decimal('299.99'),
            price_per_storefront=Decimal('0.00'),
            currency='GHS',
            is_active=True
        )
    print(f"✓ Pricing Tier: {tier.name}")
    
    # Create tax configurations
    taxes = [
        ('VAT', Decimal('15.00')),
        ('NHIL', Decimal('2.50')),
        ('GETFund', Decimal('2.50')),
        ('COVID-19 Levy', Decimal('1.00'))
    ]
    for tax_name, tax_rate in taxes:
        TaxConfiguration.objects.get_or_create(
            name=tax_name,
            defaults={
                'rate': tax_rate,
                'is_active': True,
                'country': 'GH'
            }
        )
    print(f"✓ Taxes: {len(taxes)} configured")
    
    # Create service charges
    ServiceCharge.objects.get_or_create(
        name='Paystack Fee',
        defaults={
            'rate': Decimal('1.50'),
            'flat_fee': Decimal('0.00'),
            'is_active': True,
            'gateway': 'PAYSTACK'
        }
    )
    print(f"✓ Service Charges: Configured")
    
    return user, business, plan

def test_create_subscription(user, business, plan):
    """Test creating a subscription"""
    print("\n" + "="*60)
    print("TEST 1: Create Subscription")
    print("="*60)
    
    factory = RequestFactory()
    request = factory.post(
        '/api/subscriptions/',
        data=json.dumps({
            'plan': str(plan.id),
            'business': str(business.id)
        }),
        content_type='application/json'
    )
    force_authenticate(request, user=user)
    
    view = SubscriptionViewSet.as_view({'post': 'create'})
    response = view(request)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 201:
        data = response.data
        print(f"✓ Subscription Created: {data['id']}")
        print(f"  - Status: {data['status']}")
        print(f"  - Payment Status: {data['payment_status']}")
        print(f"  - Plan: {data['plan']['name']}")
        return data['id']
    else:
        print(f"✗ Error: {response.data}")
        return None

def test_initialize_payment(user, subscription_id):
    """Test initializing payment"""
    print("\n" + "="*60)
    print("TEST 2: Initialize Payment")
    print("="*60)
    
    factory = RequestFactory()
    request = factory.post(
        f'/api/subscriptions/{subscription_id}/initialize_payment/',
        data=json.dumps({
            'gateway': 'PAYSTACK',
            'callback_url': 'http://localhost:3000/verify'
        }),
        content_type='application/json'
    )
    force_authenticate(request, user=user)
    
    view = SubscriptionViewSet.as_view({'post': 'initialize_payment'})
    response = view(request, pk=subscription_id)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.data
        print(f"✓ Payment Initialized")
        print(f"  - Payment ID: {data.get('payment_id')}")
        print(f"  - Reference: {data.get('reference')}")
        print(f"  - Amount: {data.get('amount')} {data.get('currency')}")
        print(f"  - Authorization URL: {data.get('authorization_url')}")
        
        if 'pricing_breakdown' in data:
            breakdown = data['pricing_breakdown']
            print(f"\n  Pricing Breakdown:")
            print(f"  - Base Price: {breakdown.get('base_price')}")
            print(f"  - Storefront Count: {breakdown.get('storefront_count')}")
            print(f"  - Total Tax: {breakdown.get('total_tax')}")
            print(f"  - Total Service Charges: {breakdown.get('total_service_charges')}")
            print(f"  - Taxes: {len(breakdown.get('taxes', []))} items")
            print(f"  - Service Charges: {len(breakdown.get('service_charges', []))} items")
        
        return data.get('reference')
    else:
        print(f"✗ Error: {response.data}")
        return None

def check_payment_record(reference):
    """Check if payment record was created"""
    print("\n" + "="*60)
    print("VERIFICATION: Check Payment Record")
    print("="*60)
    
    payment = SubscriptionPayment.objects.filter(
        transaction_reference=reference
    ).first()
    
    if payment:
        print(f"✓ Payment Record Found")
        print(f"  - ID: {payment.id}")
        print(f"  - Amount: {payment.amount} {payment.currency}")
        print(f"  - Status: {payment.status}")
        print(f"  - Base Amount: {payment.base_amount}")
        print(f"  - Total Tax: {payment.total_tax_amount}")
        print(f"  - Total Service Charges: {payment.total_service_charges}")
        print(f"  - Storefront Count: {payment.storefront_count}")
        
        if payment.tax_breakdown:
            print(f"  - Tax Breakdown: {len(payment.tax_breakdown)} items")
            for tax in payment.tax_breakdown:
                print(f"    • {tax.get('name')}: {tax.get('amount')}")
        
        if payment.service_charges_breakdown:
            print(f"  - Service Charges: {len(payment.service_charges_breakdown)} items")
            for charge in payment.service_charges_breakdown:
                print(f"    • {charge.get('name')}: {charge.get('amount')}")
        
        return True
    else:
        print(f"✗ Payment Record Not Found")
        return False

def print_manual_verification_steps(reference, authorization_url):
    """Print manual steps for payment verification"""
    print("\n" + "="*60)
    print("MANUAL VERIFICATION REQUIRED")
    print("="*60)
    print("\nTo complete the payment flow:")
    print(f"\n1. Visit this URL in your browser:")
    print(f"   {authorization_url}")
    print("\n2. Use test card details:")
    print("   Card Number: 5531886652142950")
    print("   CVV: 564")
    print("   PIN: 3310")
    print("\n3. Complete the payment")
    print("\n4. Run the verification test:")
    print(f"   python test_verify_payment.py {reference}")
    print("\n" + "="*60)

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SUBSCRIPTION PAYMENT API TEST SUITE")
    print("="*60)
    
    try:
        # Setup test data
        user, business, plan = setup_test_data()
        
        # Test 1: Create Subscription
        subscription_id = test_create_subscription(user, business, plan)
        if not subscription_id:
            print("\n✗ Test suite aborted: Failed to create subscription")
            return
        
        # Test 2: Initialize Payment
        reference = test_initialize_payment(user, subscription_id)
        if not reference:
            print("\n✗ Test suite aborted: Failed to initialize payment")
            return
        
        # Verification: Check Payment Record
        payment_exists = check_payment_record(reference)
        if not payment_exists:
            print("\n⚠ Warning: Payment record not created properly")
        
        # Get authorization URL for manual testing
        payment = SubscriptionPayment.objects.get(transaction_reference=reference)
        authorization_url = payment.gateway_response.get('data', {}).get('authorization_url', 'N/A')
        
        # Print manual verification steps
        print_manual_verification_steps(reference, authorization_url)
        
        print("\n" + "="*60)
        print("TEST SUITE COMPLETED")
        print("="*60)
        print("\n✓ All automated tests passed!")
        print("⚠ Manual payment completion required for full verification")
        print(f"\nSubscription ID: {subscription_id}")
        print(f"Payment Reference: {reference}")
        print("\n")
        
    except Exception as e:
        print(f"\n✗ Test suite failed with error:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
