#!/usr/bin/env python
"""
Quick test to verify URL patterns are correctly configured
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/home/teejay/Documents/Projects/pos/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.urls import resolve, reverse
from django.urls.exceptions import Resolver404

# Test URLs
test_urls = [
    '/reports/api/automation/schedules/',
    '/reports/api/automation/history/',
    '/reports/api/automation/history/statistics/',
    '/reports/api/automation/notifications/',
    '/reports/api/sales/export/',
    '/reports/api/customers/export/',
    '/reports/api/inventory/export/',
    '/reports/api/audit/export/',
]

print("=" * 70)
print("URL PATTERN VERIFICATION")
print("=" * 70)

for url in test_urls:
    try:
        match = resolve(url)
        status = "✅ FOUND"
        view = match.url_name or match.func.__name__
        print(f"{status:12} {url:50} -> {view}")
    except Resolver404:
        print(f"❌ NOT FOUND {url}")

print("\n" + "=" * 70)
print("REVERSE URL LOOKUP (Testing Named Routes)")
print("=" * 70)

named_urls = [
    'export-schedule-list',
    'export-history-list',
    'export-notifications',
    'sales-export',
    'customer-export',
    'inventory-export',
    'audit-log-export',
]

for name in named_urls:
    try:
        url = reverse(name)
        print(f"✅ {name:30} -> {url}")
    except Exception as e:
        print(f"❌ {name:30} -> ERROR: {e}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)

# Final test - the endpoint that was failing
failing_endpoint = '/reports/api/automation/history/statistics/'
try:
    match = resolve(failing_endpoint)
    print(f"\n✅ SUCCESS! The previously failing endpoint now works:")
    print(f"   {failing_endpoint}")
    print(f"   View: {match.func.__name__}")
    print(f"\n   Frontend should use: GET {failing_endpoint}")
except Resolver404:
    print(f"\n❌ FAILED! Endpoint still not found:")
    print(f"   {failing_endpoint}")
    print(f"   Check reports/urls.py configuration")
