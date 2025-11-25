#!/usr/bin/env python
"""
Generate secure keys for Django and other services
Use this script to rotate compromised credentials
"""

import secrets
import string
from django.core.management.utils import get_random_secret_key


def generate_django_secret_key():
    """Generate a secure Django SECRET_KEY"""
    return get_random_secret_key()


def generate_strong_password(length=32):
    """Generate a strong random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def generate_api_key(prefix='sk', length=48):
    """Generate an API key with prefix"""
    random_part = secrets.token_urlsafe(length)
    return f"{prefix}_{random_part}"


def generate_webhook_secret(length=64):
    """Generate webhook secret"""
    return secrets.token_hex(length)


if __name__ == '__main__':
    print("=" * 80)
    print("SECURE KEY GENERATOR")
    print("=" * 80)
    print("\n⚠️  IMPORTANT: Store these securely and never commit to git!\n")
    
    print("1. Django SECRET_KEY:")
    print(f"   SECRET_KEY={generate_django_secret_key()}")
    print()
    
    print("2. Database Password:")
    print(f"   DB_PASSWORD={generate_strong_password()}")
    print()
    
    print("3. Email App Password:")
    print("   Generate via: https://myaccount.google.com/apppasswords")
    print()
    
    print("4. OpenAI API Key:")
    print("   Get from: https://platform.openai.com/api-keys")
    print()
    
    print("5. Paystack Keys:")
    print("   Get from: https://dashboard.paystack.com/settings/developer")
    print()
    
    print("6. Webhook Secrets:")
    print(f"   PAYSTACK_WEBHOOK_SECRET={generate_webhook_secret()}")
    print(f"   STRIPE_WEBHOOK_SECRET={generate_webhook_secret()}")
    print()
    
    print("7. Anonymization Salt (for GDPR):")
    print(f"   ANONYMIZATION_SALT={generate_api_key('salt', 32)}")
    print()
    
    print("=" * 80)
    print("NEXT STEPS:")
    print("1. Update .env.development with these values")
    print("2. Update .env.production with DIFFERENT values")
    print("3. Restart all services")
    print("4. Test thoroughly")
    print("=" * 80)
