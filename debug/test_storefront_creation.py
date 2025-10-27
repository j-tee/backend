#!/usr/bin/env python
"""
Test storefront creation to debug the issue
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from rest_framework.test import APIClient
from accounts.models import User, Business, BusinessMembership

# Get a user
user = User.objects.first()
if not user:
    print("❌ No users found")
    exit(1)

print(f"✅ Using user: {user.email} ({user.name})")

# Check if user is a business owner
owner_membership = BusinessMembership.objects.filter(
    user=user, 
    role=BusinessMembership.OWNER
).first()

if owner_membership:
    print(f"✅ User is OWNER of: {owner_membership.business.name}")
else:
    print(f"⚠️  User is not an owner")
    # Try to find a business owner
    owner_membership = BusinessMembership.objects.filter(
        role=BusinessMembership.OWNER
    ).first()
    
    if owner_membership:
        user = owner_membership.user
        print(f"✅ Using owner: {user.email} ({user.name}) of {owner_membership.business.name}")
    else:
        print("❌ No business owners found")
        exit(1)

# Create API client and authenticate
client = APIClient()
client.force_authenticate(user=user)

# Test creating a storefront
data = {
    'name': 'Test Store from API',
    'location': 'Test Location from API'
}

print(f"\n📤 Sending POST request to /inventory/api/storefronts/")
print(f"Data: {data}")

response = client.post('/inventory/api/storefronts/', data, format='json')

print(f"\n📥 Response Status: {response.status_code}")
if hasattr(response, 'data'):
    print(f"Response Data: {response.data}")
else:
    print(f"Response Content: {response.content}")

if response.status_code == 201:
    print("✅ Storefront created successfully!")
    if hasattr(response, 'data'):
        print(f"   ID: {response.data.get('id')}")
        print(f"   Name: {response.data.get('name')}")
else:
    print("❌ Failed to create storefront")
    if hasattr(response, 'data'):
        if 'user' in response.data:
            print(f"   Error on 'user' field: {response.data['user']}")
        if '0' in response.data:
            print(f"   Error on '0' field: {response.data['0']}")
