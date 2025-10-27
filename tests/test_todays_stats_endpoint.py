"""Tests for the dedicated today's stats endpoint."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

TODAYS_STATS_URL = '/sales/api/sales/todays-stats/'
SUMMARY_URL = '/sales/api/sales/summary/'


def _quantize(value):
    return Decimal(str(value)).quantize(Decimal('0.01'))


def test_todays_stats_endpoint_matches_summary():
    """Verify the dedicated endpoint aligns with the summary data for today."""
    user = User.objects.first()
    assert user, "Test requires at least one user in the database."

    client = APIClient()
    client.force_authenticate(user=user)

    todays_response = client.get(TODAYS_STATS_URL)
    assert todays_response.status_code == 200
    todays_data = todays_response.json()

    for field in ['transactions', 'total_sales', 'avg_transaction', 'cash_at_hand', 'accounts_receivable']:
        assert field in todays_data, f"Missing field '{field}' in today's stats response"

    summary_response = client.get(SUMMARY_URL, {'date_range': 'today', 'status': 'COMPLETED'})
    assert summary_response.status_code == 200
    summary_data = summary_response.json()['summary']

    assert todays_data['transactions'] == summary_data['total_transactions'], "Transaction counts differ"
    assert _quantize(todays_data['total_sales']) == _quantize(summary_data['total_sales']), "Total sales mismatch"

    if summary_data.get('avg_transaction') is None:
        assert todays_data['avg_transaction'] == 0.0
    else:
        assert _quantize(todays_data['avg_transaction']) == _quantize(summary_data['avg_transaction'])

    assert _quantize(todays_data['cash_at_hand']) == _quantize(summary_data['cash_at_hand'])
    assert _quantize(todays_data['accounts_receivable']) == _quantize(summary_data['accounts_receivable'])


def test_todays_stats_endpoint_custom_statuses():
    """The endpoint should respect explicit status filters."""
    user = User.objects.first()
    assert user, "Test requires at least one user in the database."

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(TODAYS_STATS_URL, {'status': ['COMPLETED', 'PARTIAL']})
    assert response.status_code == 200
    data = response.json()

    assert data['statuses'] == ['COMPLETED', 'PARTIAL']

    # The payment breakdown should include only the requested statuses.
    status_set = set(data['statuses'])
    summary_response = client.get(
        SUMMARY_URL,
        {'date_range': 'today', 'status': ['COMPLETED', 'PARTIAL']}
    )
    assert summary_response.status_code == 200
    summary_total_transactions = summary_response.json()['summary']['total_transactions']
    assert data['transactions'] == summary_total_transactions


if __name__ == '__main__':
    test_todays_stats_endpoint_matches_summary()
    test_todays_stats_endpoint_custom_statuses()
    print("✅ Today's stats endpoint tests passed")