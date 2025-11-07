#!/usr/bin/env python
"""
Script to delete all AI credit related records from the database

This will delete:
- BusinessAICredits (credit balances)
- AITransaction (usage logs)
- AICreditPurchase (purchase history)
- AIUsageAlert (alert records)

Usage:
    python delete_ai_credits.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from ai_features.models import BusinessAICredits, AITransaction, AICreditPurchase, AIUsageAlert


def delete_all_ai_credits():
    """Delete all AI credit related records"""
    
    print("\n" + "="*60)
    print("  AI CREDITS DATABASE CLEANUP")
    print("="*60 + "\n")
    
    # Count records before deletion
    credits_count = BusinessAICredits.objects.count()
    transactions_count = AITransaction.objects.count()
    purchases_count = AICreditPurchase.objects.count()
    alerts_count = AIUsageAlert.objects.count()
    total_count = credits_count + transactions_count + purchases_count + alerts_count
    
    print("📊 Records to delete:")
    print(f"   - Business AI Credits: {credits_count}")
    print(f"   - AI Transactions: {transactions_count}")
    print(f"   - AI Credit Purchases: {purchases_count}")
    print(f"   - AI Usage Alerts: {alerts_count}")
    print(f"   - TOTAL: {total_count}")
    print()
    
    if total_count == 0:
        print("✅ No records to delete. Database is already clean.")
        return
    
    # Confirm deletion
    response = input("⚠️  Are you sure you want to delete ALL AI credit records? (yes/no): ")
    
    if response.lower() != 'yes':
        print("\n❌ Deletion cancelled.")
        return
    
    print("\n🗑️  Deleting records...")
    
    # Delete in order (to avoid foreign key constraints)
    try:
        # 1. Delete alerts (no dependencies)
        deleted = AIUsageAlert.objects.all().delete()
        print(f"   ✓ AI Usage Alerts deleted: {deleted[0]} records")
        
        # 2. Delete transactions (references business and user)
        deleted = AITransaction.objects.all().delete()
        print(f"   ✓ AI Transactions deleted: {deleted[0]} records")
        
        # 3. Delete purchases (references business and user)
        deleted = AICreditPurchase.objects.all().delete()
        print(f"   ✓ AI Credit Purchases deleted: {deleted[0]} records")
        
        # 4. Delete credits (references business)
        deleted = BusinessAICredits.objects.all().delete()
        print(f"   ✓ Business AI Credits deleted: {deleted[0]} records")
        
        print("\n✅ All AI credit records deleted successfully!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error during deletion: {str(e)}")
        print("Some records may have been deleted before the error occurred.")
        sys.exit(1)


if __name__ == "__main__":
    delete_all_ai_credits()
