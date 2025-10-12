#!/usr/bin/env python
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from sales.serializers import SaleSerializer
from sales.models import StoreFront, Customer
from accounts.models import User

# Get test data
storefront = StoreFront.objects.first()
customer = Customer.objects.filter(name__icontains='walk').first()

print("\n" + "="*60)
print("TEST SALE CREATION WITH MINIMAL PAYLOAD")
print("="*60)

# Test 1: Minimal payload (what frontend is sending)
print("\n📝 Test 1: Minimal Payload (Frontend Style)")
payload1 = {
    "storefront": str(storefront.id),
    "customer": str(customer.id) if customer else None,
    "type": "RETAIL",
    "discount_amount": 0,
    "tax_amount": 0,
    "subtotal": 0,
    "total_amount": 0,
    "amount_due": 0,
    "amount_paid": 0
}

print(f"Payload: {json.dumps(payload1, indent=2)}")

serializer1 = SaleSerializer(data=payload1)
if serializer1.is_valid():
    print("✅ Validation PASSED")
    print(f"Validated data: {serializer1.validated_data}")
else:
    print("❌ Validation FAILED")
    print(f"Errors: {serializer1.errors}")

# Test 2: Even more minimal (without amount fields)
print("\n📝 Test 2: Super Minimal Payload (Only Required Fields)")
payload2 = {
    "storefront": str(storefront.id),
    "type": "RETAIL"
}

print(f"Payload: {json.dumps(payload2, indent=2)}")

serializer2 = SaleSerializer(data=payload2)
if serializer2.is_valid():
    print("✅ Validation PASSED")
    print(f"Validated data: {serializer2.validated_data}")
else:
    print("❌ Validation FAILED")
    print(f"Errors: {serializer2.errors}")

print("\n" + "="*60)
