#!/usr/bin/env python
"""
Quick script to create a test user for development login.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from accounts.models import User

print("=" * 70)
print("Creating Test User for Development")
print("=" * 70)

# Create or update user
email = 'mikedit009@gmail.com'
password = 'TestPass123!'

try:
    user, created = User.objects.update_or_create(
        email=email,
        defaults={
            'name': 'Mike Edit',
            'email_verified': True,
            'is_active': True,
            'account_type': User.ACCOUNT_OWNER
        }
    )
    
    if created:
        user.set_password(password)
        user.save()
        print(f"\n✅ SUCCESS: Created new user")
    else:
        # Update password for existing user
        user.set_password(password)
        user.email_verified = True
        user.is_active = True
        user.save()
        print(f"\n✅ SUCCESS: Updated existing user")
    
    print(f"\nUser Details:")
    print(f"  Email: {user.email}")
    print(f"  Name: {user.name}")
    print(f"  Email Verified: {user.email_verified}")
    print(f"  Active: {user.is_active}")
    print(f"  Account Type: {user.account_type}")
    
    print(f"\n🔐 Login Credentials:")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    
    print(f"\n🚀 You can now login at: http://localhost:5173/login")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
