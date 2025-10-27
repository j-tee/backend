#!/usr/bin/env python3
"""
Debug script to check user's business associations
Run this to verify if the user has proper business memberships
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from accounts.models import User, BusinessMembership, Business

def check_user_business(email):
    """Check user's business associations"""
    try:
        user = User.objects.get(email=email)
        print(f"\n{'='*60}")
        print(f"USER INFORMATION")
        print(f"{'='*60}")
        print(f"Email: {user.email}")
        print(f"Is Active: {user.is_active}")
        print(f"Is Staff: {user.is_staff}")
        
        print(f"\n{'='*60}")
        print(f"BUSINESS ASSOCIATIONS")
        print(f"{'='*60}")
        
        # Check primary_business property
        primary = user.primary_business
        print(f"\nPrimary Business:")
        if primary:
            print(f"  ✅ Name: {primary.name}")
            print(f"  ✅ ID: {primary.id}")
            print(f"  ✅ Is Active: {primary.is_active}")
        else:
            print(f"  ❌ NO PRIMARY BUSINESS FOUND")
        
        # Check all business memberships
        memberships = BusinessMembership.objects.filter(user=user)
        print(f"\nAll Business Memberships: {memberships.count()}")
        
        for i, membership in enumerate(memberships, 1):
            print(f"\n  Membership #{i}:")
            print(f"    Business: {membership.business.name}")
            print(f"    Business ID: {membership.business.id}")
            print(f"    Role: {membership.role}")
            print(f"    Is Active: {'✅' if membership.is_active else '❌'} {membership.is_active}")
            print(f"    Created: {membership.created_at}")
        
        # Check active memberships
        active_memberships = BusinessMembership.objects.filter(user=user, is_active=True)
        print(f"\nActive Memberships: {active_memberships.count()}")
        
        if active_memberships.count() == 0:
            print("\n" + "="*60)
            print("⚠️  WARNING: NO ACTIVE BUSINESS MEMBERSHIPS FOUND!")
            print("="*60)
            print("\nThis user will get 403 Forbidden on all report endpoints.")
            print("\nTo fix, run:")
            print("  python manage.py shell")
            print("  from accounts.models import User, BusinessMembership, Business")
            print(f"  user = User.objects.get(email='{email}')")
            print("  business = Business.objects.first()  # or get specific business")
            print("  BusinessMembership.objects.create(")
            print("      user=user,")
            print("      business=business,")
            print("      is_active=True,")
            print("      role='OWNER'")
            print("  )")
        
        print(f"\n{'='*60}")
        print(f"get_business_id() SIMULATION")
        print(f"{'='*60}")
        
        # Simulate what get_business_id() does
        if hasattr(user, 'primary_business') and user.primary_business:
            business_id = user.primary_business.id
            print(f"✅ Would return: {business_id} (from primary_business)")
        elif hasattr(user, 'business_memberships'):
            membership = user.business_memberships.filter(is_active=True).first()
            if membership:
                business_id = membership.business.id
                print(f"✅ Would return: {business_id} (from business_memberships)")
            else:
                print(f"❌ Would return: None (no active memberships)")
        else:
            print(f"❌ Would return: None (no business_memberships attribute)")
        
        print()
        
    except User.DoesNotExist:
        print(f"\n❌ ERROR: User with email '{email}' not found!")
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")

if __name__ == '__main__':
    # Check the user having issues
    check_user_business('mikedlt009@gmail.com')
    
    # Show all users with businesses for reference
    print(f"\n{'='*60}")
    print(f"ALL USERS WITH BUSINESSES")
    print(f"{'='*60}")
    
    all_users = User.objects.filter(business_memberships__isnull=False).distinct()
    for user in all_users:
        active_count = user.business_memberships.filter(is_active=True).count()
        total_count = user.business_memberships.count()
        print(f"  {user.email}: {active_count}/{total_count} active memberships")
