#!/usr/bin/env python
"""
Delete AI Credit Purchases and Credits for a specific business

This script will:
1. Find the business by name
2. Delete all AI credit purchases for that business
3. Delete all AI credit balances for that business
4. Delete all AI transactions for that business
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from accounts.models import Business
from ai_features.models import AICreditPurchase, BusinessAICredits, AITransaction

def delete_business_ai_data(business_name):
    """Delete all AI data for a business"""
    print(f"\n{'='*60}")
    print(f"Deleting AI Credit Data for: {business_name}")
    print(f"{'='*60}\n")
    
    # Find business
    try:
        business = Business.objects.get(name__icontains=business_name)
        print(f"✅ Found business: {business.name}")
        print(f"   Business ID: {business.id}")
    except Business.DoesNotExist:
        print(f"❌ Business not found: {business_name}")
        print("\nAvailable businesses:")
        for b in Business.objects.all()[:10]:
            print(f"   - {b.name}")
        return
    except Business.MultipleObjectsReturned:
        print(f"❌ Multiple businesses found matching '{business_name}':")
        for b in Business.objects.filter(name__icontains=business_name):
            print(f"   - {b.name} (ID: {b.id})")
        return
    
    # Count existing records
    purchases_count = AICreditPurchase.objects.filter(business=business).count()
    credits_count = BusinessAICredits.objects.filter(business=business).count()
    transactions_count = AITransaction.objects.filter(business=business).count()
    
    print(f"\nFound:")
    print(f"   {purchases_count} AI credit purchase(s)")
    print(f"   {credits_count} AI credit balance record(s)")
    print(f"   {transactions_count} AI transaction(s)")
    
    if purchases_count == 0 and credits_count == 0 and transactions_count == 0:
        print("\n✅ No AI data found for this business")
        return
    
    # Confirm deletion
    print(f"\n⚠️  WARNING: This will DELETE all AI data for {business.name}")
    print("This action cannot be undone!")
    
    confirm = input("\nType 'DELETE' to confirm: ")
    
    if confirm != 'DELETE':
        print("\n❌ Deletion cancelled")
        return
    
    # Delete data
    print("\nDeleting...")
    
    # 1. Delete purchases
    if purchases_count > 0:
        deleted_purchases = AICreditPurchase.objects.filter(business=business).delete()
        print(f"✅ Deleted {deleted_purchases[0]} purchase record(s)")
    
    # 2. Delete credit balances
    if credits_count > 0:
        deleted_credits = BusinessAICredits.objects.filter(business=business).delete()
        print(f"✅ Deleted {deleted_credits[0]} credit balance record(s)")
    
    # 3. Delete transactions
    if transactions_count > 0:
        deleted_transactions = AITransaction.objects.filter(business=business).delete()
        print(f"✅ Deleted {deleted_transactions[0]} transaction record(s)")
    
    # Clear cache
    from django.core.cache import cache
    cache_key = f"ai_credits_balance_{business.id}"
    cache.delete(cache_key)
    print(f"✅ Cleared cache")
    
    print(f"\n{'='*60}")
    print("✅ SUCCESS! All AI data deleted")
    print(f"{'='*60}\n")
    print(f"Business '{business.name}' now has:")
    print(f"   - 0 purchase records")
    print(f"   - 0 credit balance")
    print(f"   - 0 transaction history")
    print(f"\nYou can now test fresh AI credit purchases for this business.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        business_name = " ".join(sys.argv[1:])
    else:
        business_name = "Data Logique Systems"
    
    delete_business_ai_data(business_name)
