"""
Paystack Payment Integration for AI Credits
Handles credit purchases through Paystack payment gateway
"""

import requests
import hashlib
import hmac
from decimal import Decimal
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone


class PaystackException(Exception):
    """Raised when Paystack API call fails"""
    pass


class PaystackService:
    """Handle Paystack payment operations"""
    
    BASE_URL = "https://api.paystack.co"
    
    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        """Get Paystack API headers with authorization"""
        secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        
        if not secret_key:
            raise PaystackException("PAYSTACK_SECRET_KEY not configured in settings")
        
        return {
            'Authorization': f'Bearer {secret_key}',
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def initialize_transaction(
        cls,
        email: str,
        amount: Decimal,
        reference: str,
        metadata: Optional[Dict] = None,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize Paystack transaction
        
        Args:
            email: Customer email
            amount: Amount in GHS (will be converted to pesewas)
            reference: Unique transaction reference
            metadata: Optional metadata
            callback_url: Optional callback URL after payment
            
        Returns:
            dict: {
                'authorization_url': 'https://checkout.paystack.com/...',
                'access_code': 'xxx',
                'reference': 'xxx'
            }
        """
        # Convert GHS to pesewas (multiply by 100)
        amount_in_pesewas = int(amount * 100)
        
        payload = {
            'email': email,
            'amount': amount_in_pesewas,
            'reference': reference,
            'currency': 'GHS',
        }
        
        if metadata:
            payload['metadata'] = metadata
        
        if callback_url:
            payload['callback_url'] = callback_url
        
        try:
            response = requests.post(
                f"{cls.BASE_URL}/transaction/initialize",
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('status'):
                raise PaystackException(f"Paystack error: {data.get('message', 'Unknown error')}")
            
            return data['data']
        
        except requests.exceptions.RequestException as e:
            raise PaystackException(f"Failed to initialize payment: {str(e)}")
    
    @classmethod
    def verify_transaction(cls, reference: str) -> Dict[str, Any]:
        """
        Verify Paystack transaction
        
        Args:
            reference: Transaction reference to verify
            
        Returns:
            dict: {
                'status': 'success' | 'failed',
                'amount': 8000 (in pesewas),
                'currency': 'GHS',
                'reference': 'xxx',
                'paid_at': '2025-11-07T10:00:00Z',
                'customer': {'email': 'user@example.com'},
                'metadata': {...}
            }
        """
        try:
            response = requests.get(
                f"{cls.BASE_URL}/transaction/verify/{reference}",
                headers=cls._get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('status'):
                raise PaystackException(f"Paystack error: {data.get('message', 'Unknown error')}")
            
            return data['data']
        
        except requests.exceptions.RequestException as e:
            raise PaystackException(f"Failed to verify payment: {str(e)}")
    
    @classmethod
    def verify_webhook_signature(cls, payload: bytes, signature: str) -> bool:
        """
        Verify Paystack webhook signature
        
        Args:
            payload: Raw request body (bytes)
            signature: X-Paystack-Signature header value
            
        Returns:
            bool: True if signature is valid
        """
        secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        
        if not secret_key:
            return False
        
        # Compute HMAC SHA512
        computed_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    
    @classmethod
    def list_banks(cls) -> list:
        """
        Get list of supported banks for mobile money/bank transfer
        
        Returns:
            list: [{'name': 'MTN Mobile Money', 'code': 'MTN', ...}, ...]
        """
        try:
            response = requests.get(
                f"{cls.BASE_URL}/bank",
                headers=cls._get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('status'):
                return []
            
            return data.get('data', [])
        
        except requests.exceptions.RequestException:
            return []
    
    @classmethod
    def create_subscription_plan(
        cls,
        name: str,
        amount: Decimal,
        interval: str = 'monthly'
    ) -> Dict[str, Any]:
        """
        Create subscription plan (for future recurring AI credit subscriptions)
        
        Args:
            name: Plan name
            amount: Amount in GHS
            interval: 'monthly', 'quarterly', 'annually'
            
        Returns:
            dict: Plan details
        """
        amount_in_pesewas = int(amount * 100)
        
        payload = {
            'name': name,
            'amount': amount_in_pesewas,
            'interval': interval,
            'currency': 'GHS'
        }
        
        try:
            response = requests.post(
                f"{cls.BASE_URL}/plan",
                json=payload,
                headers=cls._get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('status'):
                raise PaystackException(f"Paystack error: {data.get('message', 'Unknown error')}")
            
            return data['data']
        
        except requests.exceptions.RequestException as e:
            raise PaystackException(f"Failed to create plan: {str(e)}")


def generate_payment_reference(prefix: str = "AI-CREDIT") -> str:
    """
    Generate unique payment reference with collision detection
    
    Args:
        prefix: Reference prefix
        
    Returns:
        str: Unique reference like "AI-CREDIT-1699357200-abc123"
    """
    import time
    import secrets
    import uuid
    from ..models import AICreditPurchase
    
    max_attempts = 10
    
    for _ in range(max_attempts):
        # Use timestamp + UUID for better uniqueness
        timestamp = int(time.time() * 1000)  # milliseconds for more precision
        unique_id = uuid.uuid4().hex[:8]
        reference = f"{prefix}-{timestamp}-{unique_id}"
        
        # Check if reference already exists
        if not AICreditPurchase.objects.filter(payment_reference=reference).exists():
            return reference
    
    # Fallback: use pure UUID if all attempts fail
    return f"{prefix}-{uuid.uuid4().hex}"
