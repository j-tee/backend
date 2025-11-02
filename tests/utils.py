from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from subscriptions.models import Subscription, SubscriptionPlan


def ensure_active_subscription(business):
    """Ensure the given business has an active subscription for test purposes."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name="Test Active Plan",
        defaults={
            "description": "Test subscription plan for automated tests",
            "price": Decimal("0.00"),
            "currency": "GHS",
            "billing_cycle": "MONTHLY",
        },
    )

    now = timezone.now()
    Subscription.objects.update_or_create(
        business=business,
        defaults={
            "plan": plan,
            "amount": Decimal("0.00"),
            "payment_method": "PAYSTACK",
            "payment_status": "PAID",
            "status": "ACTIVE",
            "start_date": now.date() - timedelta(days=1),
            "end_date": now.date() + timedelta(days=30),
            "current_period_start": now - timedelta(days=1),
            "current_period_end": now + timedelta(days=30),
            "auto_renew": True,
            "cancel_at_period_end": False,
            "next_billing_date": now.date() + timedelta(days=30),
            "is_trial": False,
            "grace_period_days": 7,
        },
    )
