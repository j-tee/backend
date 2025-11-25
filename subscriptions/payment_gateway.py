"""
Payment Gateway Integration with Automatic Failover
Supports Paystack and Stripe with circuit breaker pattern
"""

import logging
import time
from decimal import Decimal
from typing import Dict, Optional, List
from collections import defaultdict
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """Base exception for payment gateway errors"""
    pass


class AllGatewaysFailedError(PaymentGatewayError):
    """Raised when all configured gateways fail"""
    pass


class GatewayCircuitBreaker:
    """
    Circuit breaker pattern for payment gateways
    Prevents repeated calls to failing gateways
    """
    
    def __init__(self, failure_threshold=5, timeout=300):
        """
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before retrying (default 5 minutes)
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = defaultdict(int)
        self.last_failure = {}
        self.circuit_open = {}
    
    def is_available(self, gateway: str) -> bool:
        """Check if gateway is available (circuit closed)"""
        if gateway not in self.circuit_open:
            return True
        
        # Check if circuit is open
        if self.circuit_open[gateway]:
            # Check if timeout has passed
            time_since_failure = time.time() - self.last_failure.get(gateway, 0)
            if time_since_failure >= self.timeout:
                logger.info(f"Circuit breaker timeout passed for {gateway}, retrying")
                self.reset(gateway)
                return True
            return False
        
        return True
    
    def record_failure(self, gateway: str):
        """Record a failure and potentially open circuit"""
        self.failures[gateway] += 1
        self.last_failure[gateway] = time.time()
        
        if self.failures[gateway] >= self.failure_threshold:
            self.circuit_open[gateway] = True
            logger.error(
                f"Circuit breaker OPENED for {gateway} after "
                f"{self.failures[gateway]} failures"
            )
    
    def record_success(self, gateway: str):
        """Record a success and reset circuit"""
        if gateway in self.failures and self.failures[gateway] > 0:
            logger.info(f"Circuit breaker reset for {gateway} after successful call")
        self.reset(gateway)
    
    def reset(self, gateway: str):
        """Reset circuit breaker for gateway"""
        self.failures[gateway] = 0
        self.circuit_open[gateway] = False


# Global circuit breaker instance
circuit_breaker = GatewayCircuitBreaker()


class PaymentGatewayRouter:
    """
    Routes payment requests to appropriate gateway with failover
    """
    
    def __init__(self):
        self.gateways = ['paystack', 'stripe']
    
    def select_gateway(self, business, amount: Decimal, preferred: Optional[str] = None) -> str:
        """
        Select best gateway based on business, amount, and availability
        
        Args:
            business: Business model instance
            amount: Payment amount
            preferred: Preferred gateway if specified
        
        Returns:
            Gateway name ('paystack' or 'stripe')
        """
        # Use preferred if specified and available
        if preferred and circuit_breaker.is_available(preferred):
            return preferred
        
        # Check business country for local payment methods
        business_country = getattr(business, 'country', 'GH')
        
        # Paystack is better for Ghana/West Africa
        if business_country in ['GH', 'NG', 'ZA', 'KE'] and circuit_breaker.is_available('paystack'):
            return 'paystack'
        
        # For small amounts, use gateway with lower fees
        if amount < Decimal('1000') and circuit_breaker.is_available('paystack'):
            return 'paystack'  # Paystack has lower fees for small amounts
        
        # Default to first available gateway
        for gateway in self.gateways:
            if circuit_breaker.is_available(gateway):
                return gateway
        
        raise AllGatewaysFailedError("No payment gateways available")
    
    def process_payment_with_failover(
        self,
        business,
        amount: Decimal,
        currency: str = 'GHS',
        metadata: Optional[Dict] = None,
        preferred_gateway: Optional[str] = None
    ) -> Dict:
        """
        Process payment with automatic failover
        
        Args:
            business: Business model instance
            amount: Payment amount
            currency: Currency code
            metadata: Additional payment metadata
            preferred_gateway: Preferred gateway to try first
        
        Returns:
            Payment result dictionary
        
        Raises:
            AllGatewaysFailedError: If all gateways fail
        """
        # Determine gateway priority
        gateways = []
        if preferred_gateway:
            gateways.append(preferred_gateway)
        
        # Add other gateways based on selection logic
        primary = self.select_gateway(business, amount)
        if primary not in gateways:
            gateways.append(primary)
        
        # Add remaining gateways as backup
        for gw in self.gateways:
            if gw not in gateways:
                gateways.append(gw)
        
        last_error = None
        
        # Try each gateway in order
        for gateway in gateways:
            if not circuit_breaker.is_available(gateway):
                logger.warning(f"Skipping {gateway} - circuit breaker open")
                continue
            
            try:
                logger.info(f"Attempting payment via {gateway}")
                result = self._process_via_gateway(
                    gateway,
                    business,
                    amount,
                    currency,
                    metadata
                )
                
                circuit_breaker.record_success(gateway)
                logger.info(f"Payment successful via {gateway}")
                
                return {
                    'success': True,
                    'gateway': gateway,
                    'transaction_id': result.get('transaction_id'),
                    'reference': result.get('reference'),
                    'data': result
                }
            
            except Exception as e:
                logger.error(f"Payment failed via {gateway}: {str(e)}")
                circuit_breaker.record_failure(gateway)
                last_error = e
                continue
        
        # All gateways failed
        raise AllGatewaysFailedError(
            f"All payment gateways failed. Last error: {str(last_error)}"
        )
    
    def _process_via_gateway(
        self,
        gateway: str,
        business,
        amount: Decimal,
        currency: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """
        Process payment through specific gateway
        
        Args:
            gateway: Gateway name ('paystack' or 'stripe')
            business: Business model instance
            amount: Payment amount
            currency: Currency code
            metadata: Payment metadata
        
        Returns:
            Gateway response dictionary
        """
        if gateway == 'paystack':
            return self._process_paystack(business, amount, currency, metadata)
        elif gateway == 'stripe':
            return self._process_stripe(business, amount, currency, metadata)
        else:
            raise ValueError(f"Unknown gateway: {gateway}")
    
    def _process_paystack(
        self,
        business,
        amount: Decimal,
        currency: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """Process payment via Paystack"""
        import requests
        
        # Convert amount to kobo (Paystack uses smallest currency unit)
        amount_kobo = int(amount * 100)
        
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'amount': amount_kobo,
            'currency': currency,
            'email': business.email,
            'metadata': metadata or {}
        }
        
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            raise PaymentGatewayError(f"Paystack error: {response.text}")
        
        data = response.json()
        if not data.get('status'):
            raise PaymentGatewayError(f"Paystack failed: {data.get('message')}")
        
        return data.get('data', {})
    
    def _process_stripe(
        self,
        business,
        amount: Decimal,
        currency: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """Process payment via Stripe"""
        import stripe
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Convert amount to cents
        amount_cents = int(amount * 100)
        
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata or {},
                description=f"Subscription payment for {business.name}"
            )
            
            return {
                'transaction_id': intent.id,
                'reference': intent.id,
                'client_secret': intent.client_secret,
                'status': intent.status
            }
        
        except stripe.error.StripeError as e:
            raise PaymentGatewayError(f"Stripe error: {str(e)}")


# Global router instance
payment_router = PaymentGatewayRouter()
