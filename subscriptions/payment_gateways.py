"""
Payment Gateway Integrations
Handles Paystack and Stripe payment processing with environment variable configuration
"""
import requests
import stripe
import logging
import os
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import PaymentGatewayConfig, SubscriptionPayment, WebhookEvent

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """Base exception for payment gateway errors"""
    pass


def get_payment_mode():
    """Get payment gateway mode from environment (test or live)"""
    return os.getenv('PAYMENT_GATEWAY_MODE', 'test').lower()


class PaystackGateway:
    """Paystack payment gateway integration (Mobile Money for Ghana)"""
    
    BASE_URL = "https://api.paystack.co"
    
    def __init__(self):
        """Initialize Paystack with keys from environment variables"""
        self.mode = get_payment_mode()
        
        # Get keys based on mode
        if self.mode == 'live':
            self.public_key = os.getenv('PAYSTACK_PUBLIC_KEY_LIVE')
            self.secret_key = os.getenv('PAYSTACK_SECRET_KEY_LIVE')
            self.webhook_secret = os.getenv('PAYSTACK_WEBHOOK_SECRET_LIVE')
        else:
            self.public_key = os.getenv('PAYSTACK_PUBLIC_KEY_TEST')
            self.secret_key = os.getenv('PAYSTACK_SECRET_KEY_TEST')
            self.webhook_secret = os.getenv('PAYSTACK_WEBHOOK_SECRET_TEST')
        
        # Validate that keys are present
        if not self.secret_key:
            raise PaymentGatewayError(
                f"Paystack {self.mode} secret key not found in environment variables. "
                f"Please set PAYSTACK_SECRET_KEY_{self.mode.upper()} in your .env file"
            )
        
        if not self.public_key:
            logger.warning(f"Paystack {self.mode} public key not found in environment variables")
        
        self.test_mode = (self.mode == 'test')
        
        logger.info(f"Paystack gateway initialized in {self.mode.upper()} mode")
    
    def _make_request(self, method, endpoint, data=None):
        """Make API request to Paystack"""
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=data, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack API error ({self.mode} mode): {str(e)}")
            raise PaymentGatewayError(f"Paystack API error: {str(e)}")
    
    def initialize_payment(self, subscription, callback_url):
        """Initialize payment transaction"""
        # Convert amount to kobo (Paystack uses smallest currency unit)
        amount_in_kobo = int(subscription.amount * 100)
        
        data = {
            "email": subscription.user.email,
            "amount": amount_in_kobo,
            "currency": subscription.plan.currency,
            "reference": f"SUB_{subscription.id}_{timezone.now().timestamp()}",
            "callback_url": callback_url,
            "metadata": {
                "subscription_id": str(subscription.id),
                "plan_name": subscription.plan.name,
                "business_name": subscription.business.name if subscription.business else "",
                "user_id": str(subscription.user.id)
            }
        }
        
        try:
            response = self._make_request("POST", "transaction/initialize", data)
            
            if response.get('status'):
                return {
                    'success': True,
                    'authorization_url': response['data']['authorization_url'],
                    'access_code': response['data']['access_code'],
                    'reference': response['data']['reference']
                }
            else:
                raise PaymentGatewayError(response.get('message', 'Payment initialization failed'))
        except Exception as e:
            logger.error(f"Paystack initialization error: {str(e)}")
            raise PaymentGatewayError(f"Failed to initialize payment: {str(e)}")
    
    def verify_payment(self, reference):
        """Verify payment transaction"""
        try:
            response = self._make_request("GET", f"transaction/verify/{reference}")
            
            if response.get('status') and response.get('data'):
                data = response['data']
                return {
                    'success': data['status'] == 'success',
                    'amount': Decimal(data['amount']) / 100,  # Convert from kobo
                    'currency': data['currency'],
                    'reference': data['reference'],
                    'transaction_id': data['id'],
                    'paid_at': data['paid_at'],
                    'channel': data['channel'],
                    'metadata': data.get('metadata', {}),
                    'raw_response': data
                }
            else:
                raise PaymentGatewayError('Verification failed')
        except Exception as e:
            logger.error(f"Paystack verification error: {str(e)}")
            raise PaymentGatewayError(f"Failed to verify payment: {str(e)}")
    
    def create_subscription_payment(self, subscription, verification_data):
        """Create SubscriptionPayment record from verified payment"""
        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            amount=verification_data['amount'],
            payment_method='PAYSTACK',
            status='SUCCESSFUL',
            transaction_id=str(verification_data['transaction_id']),
            gateway_reference=verification_data['reference'],
            gateway_response=verification_data['raw_response'],
            payment_date=timezone.now(),
            billing_period_start=subscription.current_period_start.date(),
            billing_period_end=subscription.current_period_end.date()
        )
        
        # Update subscription
        subscription.payment_status = 'PAID'
        subscription.status = 'ACTIVE'
        subscription.payment_method = 'PAYSTACK'
        subscription.save()
        
        return payment
    
    def process_webhook(self, event_data, signature):
        """Process Paystack webhook event"""
        import hmac
        import hashlib
        
        # Verify webhook signature
        computed_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            msg=str(event_data).encode('utf-8'),
            digestmod=hashlib.sha512
        ).hexdigest()
        
        if computed_signature != signature:
            raise PaymentGatewayError("Invalid webhook signature")
        
        # Log webhook event
        event = WebhookEvent.objects.create(
            gateway='PAYSTACK',
            event_type=event_data.get('event'),
            event_id=event_data.get('data', {}).get('id'),
            payload=event_data,
            status='PENDING'
        )
        
        try:
            event_type = event_data.get('event')
            
            if event_type == 'charge.success':
                # Handle successful payment
                self._handle_successful_payment(event_data['data'])
            elif event_type == 'subscription.disable':
                # Handle subscription cancellation
                self._handle_subscription_cancelled(event_data['data'])
            
            event.status = 'PROCESSED'
            event.processed_at = timezone.now()
            event.save()
            
            return True
        except Exception as e:
            event.status = 'FAILED'
            event.error_message = str(e)
            event.save()
            logger.error(f"Webhook processing error: {str(e)}")
            return False
    
    def _handle_successful_payment(self, data):
        """Handle successful payment webhook"""
        reference = data.get('reference')
        metadata = data.get('metadata', {})
        subscription_id = metadata.get('subscription_id')
        
        if subscription_id:
            from .models import Subscription
            try:
                subscription = Subscription.objects.get(id=subscription_id)
                verification = self.verify_payment(reference)
                self.create_subscription_payment(subscription, verification)
            except Subscription.DoesNotExist:
                logger.error(f"Subscription not found: {subscription_id}")
    
    def _handle_subscription_cancelled(self, data):
        """Handle subscription cancellation webhook"""
        # Implementation for handling cancellation
        pass


class StripeGateway:
    """Stripe payment gateway integration (International cards)"""
    
    def __init__(self):
        """Initialize Stripe with keys from environment variables"""
        self.mode = get_payment_mode()
        
        # Get keys based on mode
        if self.mode == 'live':
            self.public_key = os.getenv('STRIPE_PUBLIC_KEY_LIVE')
            self.secret_key = os.getenv('STRIPE_SECRET_KEY_LIVE')
            self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET_LIVE')
        else:
            self.public_key = os.getenv('STRIPE_PUBLIC_KEY_TEST')
            self.secret_key = os.getenv('STRIPE_SECRET_KEY_TEST')
            self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET_TEST')
        
        # Validate that keys are present
        if not self.secret_key:
            raise PaymentGatewayError(
                f"Stripe {self.mode} secret key not found in environment variables. "
                f"Please set STRIPE_SECRET_KEY_{self.mode.upper()} in your .env file"
            )
        
        if not self.public_key:
            logger.warning(f"Stripe {self.mode} public key not found in environment variables")
        
        # Set Stripe API key
        stripe.api_key = self.secret_key
        self.test_mode = (self.mode == 'test')
        
        logger.info(f"Stripe gateway initialized in {self.mode.upper()} mode")
    
    def create_checkout_session(self, subscription, success_url, cancel_url):
        """Create Stripe checkout session"""
        try:
            # Convert amount to cents (Stripe uses smallest currency unit)
            amount_in_cents = int(subscription.amount * 100)
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': subscription.plan.currency.lower(),
                        'unit_amount': amount_in_cents,
                        'product_data': {
                            'name': subscription.plan.name,
                            'description': subscription.plan.description,
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(subscription.id),
                metadata={
                    'subscription_id': str(subscription.id),
                    'plan_id': str(subscription.plan.id),
                    'user_id': str(subscription.user.id),
                    'business_id': str(subscription.business.id) if subscription.business else '',
                }
            )
            
            return {
                'success': True,
                'session_id': session.id,
                'checkout_url': session.url,
                'session': session
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout error: {str(e)}")
            raise PaymentGatewayError(f"Failed to create checkout session: {str(e)}")
    
    def retrieve_session(self, session_id):
        """Retrieve checkout session details"""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                'success': True,
                'payment_status': session.payment_status,
                'amount_total': Decimal(session.amount_total) / 100 if session.amount_total else 0,
                'currency': session.currency,
                'customer_email': session.customer_details.email if session.customer_details else None,
                'metadata': session.metadata,
                'session': session
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe session retrieval error: {str(e)}")
            raise PaymentGatewayError(f"Failed to retrieve session: {str(e)}")
    
    def create_subscription_payment(self, subscription, session_data):
        """Create SubscriptionPayment record from Stripe session"""
        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            amount=session_data['amount_total'],
            payment_method='STRIPE',
            status='SUCCESSFUL',
            transaction_id=session_data['session'].payment_intent,
            gateway_reference=session_data['session'].id,
            gateway_response={'session': session_data['session'].to_dict()},
            payment_date=timezone.now(),
            billing_period_start=subscription.current_period_start.date(),
            billing_period_end=subscription.current_period_end.date()
        )
        
        # Update subscription
        subscription.payment_status = 'PAID'
        subscription.status = 'ACTIVE'
        subscription.payment_method = 'STRIPE'
        subscription.save()
        
        return payment
    
    def process_webhook(self, payload, signature):
        """Process Stripe webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
        except ValueError:
            raise PaymentGatewayError("Invalid webhook payload")
        except stripe.error.SignatureVerificationError:
            raise PaymentGatewayError("Invalid webhook signature")
        
        # Log webhook event
        webhook_event = WebhookEvent.objects.create(
            gateway='STRIPE',
            event_type=event['type'],
            event_id=event['id'],
            payload=event,
            status='PENDING'
        )
        
        try:
            if event['type'] == 'checkout.session.completed':
                self._handle_checkout_completed(event['data']['object'])
            elif event['type'] == 'payment_intent.succeeded':
                self._handle_payment_succeeded(event['data']['object'])
            elif event['type'] == 'payment_intent.payment_failed':
                self._handle_payment_failed(event['data']['object'])
            
            webhook_event.status = 'PROCESSED'
            webhook_event.processed_at = timezone.now()
            webhook_event.save()
            
            return True
        except Exception as e:
            webhook_event.status = 'FAILED'
            webhook_event.error_message = str(e)
            webhook_event.save()
            logger.error(f"Stripe webhook processing error: {str(e)}")
            return False
    
    def _handle_checkout_completed(self, session):
        """Handle completed checkout session"""
        subscription_id = session.get('metadata', {}).get('subscription_id')
        
        if subscription_id:
            from .models import Subscription
            try:
                subscription = Subscription.objects.get(id=subscription_id)
                session_data = self.retrieve_session(session['id'])
                self.create_subscription_payment(subscription, session_data)
            except Subscription.DoesNotExist:
                logger.error(f"Subscription not found: {subscription_id}")
    
    def _handle_payment_succeeded(self, payment_intent):
        """Handle successful payment intent"""
        # Additional handling for successful payments
        pass
    
    def _handle_payment_failed(self, payment_intent):
        """Handle failed payment intent"""
        # Handle payment failures (update subscription status, send alerts)
        pass


def get_payment_gateway(gateway_type):
    """Factory function to get appropriate payment gateway"""
    if gateway_type == 'PAYSTACK':
        return PaystackGateway()
    elif gateway_type == 'STRIPE':
        return StripeGateway()
    else:
        raise PaymentGatewayError(f"Unsupported gateway type: {gateway_type}")


def get_gateway_public_keys():
    """
    Get public keys for all payment gateways
    Used by frontend to initialize payment widgets
    """
    mode = get_payment_mode()
    
    keys = {
        'mode': mode,
        'gateways': {}
    }
    
    # Paystack public key
    if mode == 'live':
        paystack_key = os.getenv('PAYSTACK_PUBLIC_KEY_LIVE')
        stripe_key = os.getenv('STRIPE_PUBLIC_KEY_LIVE')
    else:
        paystack_key = os.getenv('PAYSTACK_PUBLIC_KEY_TEST')
        stripe_key = os.getenv('STRIPE_PUBLIC_KEY_TEST')
    
    if paystack_key:
        keys['gateways']['PAYSTACK'] = {
            'public_key': paystack_key,
            'name': 'Paystack',
            'supports': ['mobile_money', 'bank', 'card']
        }
    
    if stripe_key:
        keys['gateways']['STRIPE'] = {
            'public_key': stripe_key,
            'name': 'Stripe',
            'supports': ['card']
        }
    
    return keys


def validate_gateway_configuration():
    """
    Validate that payment gateway environment variables are properly configured
    Returns dict with validation results
    """
    mode = get_payment_mode()
    validation = {
        'mode': mode,
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'gateways': {}
    }
    
    # Check Paystack configuration
    paystack_validation = {
        'configured': False,
        'has_public_key': False,
        'has_secret_key': False,
        'has_webhook_secret': False
    }
    
    if mode == 'live':
        paystack_validation['has_public_key'] = bool(os.getenv('PAYSTACK_PUBLIC_KEY_LIVE'))
        paystack_validation['has_secret_key'] = bool(os.getenv('PAYSTACK_SECRET_KEY_LIVE'))
        paystack_validation['has_webhook_secret'] = bool(os.getenv('PAYSTACK_WEBHOOK_SECRET_LIVE'))
    else:
        paystack_validation['has_public_key'] = bool(os.getenv('PAYSTACK_PUBLIC_KEY_TEST'))
        paystack_validation['has_secret_key'] = bool(os.getenv('PAYSTACK_SECRET_KEY_TEST'))
        paystack_validation['has_webhook_secret'] = bool(os.getenv('PAYSTACK_WEBHOOK_SECRET_TEST'))
    
    paystack_validation['configured'] = all([
        paystack_validation['has_public_key'],
        paystack_validation['has_secret_key'],
        paystack_validation['has_webhook_secret']
    ])
    
    validation['gateways']['PAYSTACK'] = paystack_validation
    
    if not paystack_validation['has_secret_key']:
        validation['errors'].append(f"Paystack {mode} secret key not configured")
        validation['is_valid'] = False
    
    if not paystack_validation['has_webhook_secret']:
        validation['warnings'].append(f"Paystack {mode} webhook secret not configured (webhooks will fail)")
    
    # Check Stripe configuration
    stripe_validation = {
        'configured': False,
        'has_public_key': False,
        'has_secret_key': False,
        'has_webhook_secret': False
    }
    
    if mode == 'live':
        stripe_validation['has_public_key'] = bool(os.getenv('STRIPE_PUBLIC_KEY_LIVE'))
        stripe_validation['has_secret_key'] = bool(os.getenv('STRIPE_SECRET_KEY_LIVE'))
        stripe_validation['has_webhook_secret'] = bool(os.getenv('STRIPE_WEBHOOK_SECRET_LIVE'))
    else:
        stripe_validation['has_public_key'] = bool(os.getenv('STRIPE_PUBLIC_KEY_TEST'))
        stripe_validation['has_secret_key'] = bool(os.getenv('STRIPE_SECRET_KEY_TEST'))
        stripe_validation['has_webhook_secret'] = bool(os.getenv('STRIPE_WEBHOOK_SECRET_TEST'))
    
    stripe_validation['configured'] = all([
        stripe_validation['has_public_key'],
        stripe_validation['has_secret_key'],
        stripe_validation['has_webhook_secret']
    ])
    
    validation['gateways']['STRIPE'] = stripe_validation
    
    if not stripe_validation['has_secret_key']:
        validation['errors'].append(f"Stripe {mode} secret key not configured")
        validation['is_valid'] = False
    
    if not stripe_validation['has_webhook_secret']:
        validation['warnings'].append(f"Stripe {mode} webhook secret not configured (webhooks will fail)")
    
    return validation
