"""Tests for the Customer Segmentation API using current data models."""
import uuid
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Business
from inventory.models import Category, Product, StoreFront
from sales.models import Customer, Sale, SaleItem

User = get_user_model()


class CustomerSegmentationReportTestCase(TestCase):
    """Test suite for Customer Segmentation API endpoint."""

    def setUp(self):
        """Create a business, owner, storefront, and baseline product."""
        self.user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123',
            name='Owner User'
        )

        self.business = Business.objects.create(
            owner=self.user,
            name='Test Business',
            tin=f'TIN-{uuid.uuid4().hex[:12]}',
            email='owner@example.com',
            address='123 Market Street'
        )

        self.storefront = StoreFront.objects.create(
            user=self.user,
            name='Main Store',
            location='Downtown'
        )

        self.category = Category.objects.create(name='General')
        self.product = Product.objects.create(
            business=self.business,
            name='Test Product',
            sku='SKU-001',
            category=self.category
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = '/reports/api/customer/segmentation/'

        self._create_test_customers()
    
    def _create_test_customers(self):
        """Create customers with known RFM characteristics."""
        now = timezone.now()

        def make_customer(name, email):
            return Customer.objects.create(
                business=self.business,
                name=name,
                email=email,
                created_by=self.user
            )

        # Champion: recent, frequent, high spend
        self.champion = make_customer('Champion Customer', 'champion@example.com')
        for i in range(10):
            self._create_sale(
                customer=self.champion,
                completed_at=now - timedelta(days=2 + i),
                total_amount=Decimal('500.00')
            )

        # Loyal: consistent frequency and spend
        self.loyal = make_customer('Loyal Customer', 'loyal@example.com')
        for i in range(8):
            self._create_sale(
                customer=self.loyal,
                completed_at=now - timedelta(days=10 + i),
                total_amount=Decimal('400.00')
            )

        # At Risk: older activity with moderate spend
        self.at_risk = make_customer('At Risk Customer', 'atrisk@example.com')
        for i in range(5):
            self._create_sale(
                customer=self.at_risk,
                completed_at=now - timedelta(days=60 + i * 10),
                total_amount=Decimal('300.00')
            )

        # New Customer: very recent single purchase
        self.new_customer = make_customer('New Customer', 'new@example.com')
        self._create_sale(
            customer=self.new_customer,
            completed_at=now - timedelta(days=1),
            total_amount=Decimal('100.00')
        )

        # Hibernating: older (but within default range), infrequent, low spend
        self.hibernating = make_customer('Hibernating Customer', 'hibernating@example.com')
        for i in range(2):
            self._create_sale(
                customer=self.hibernating,
                completed_at=now - timedelta(days=80 + i * 5),
                total_amount=Decimal('75.00')
            )
    
    def _create_sale(self, *, customer, completed_at, total_amount):
        """Create a completed sale with a single line item for the customer."""
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=customer,
            status=Sale.STATUS_COMPLETED,
            type=Sale.TYPE_RETAIL,
            payment_type=Sale.PAYMENT_TYPE_CASH,
            subtotal=total_amount,
            total_amount=total_amount,
            amount_paid=total_amount,
            amount_due=Decimal('0.00'),
            amount_refunded=Decimal('0.00'),
            discount_amount=Decimal('0.00'),
            tax_amount=Decimal('0.00'),
            completed_at=completed_at
        )

        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=Decimal('1.00'),
            unit_price=total_amount,
            total_price=total_amount
        )

        return sale
    
    def test_rfm_segmentation_default_method(self):
        """Test RFM segmentation with default parameters."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        
        self.assertTrue(payload['success'])
        self.assertIn('data', payload)
        
        data = payload['data']
        self.assertEqual(data['method'], 'rfm')
        self.assertIn('insights', data)
        self.assertIn('segments', data)
    
    def test_rfm_insights_structure(self):
        """Test that insights contain all required fields."""
        response = self.client.get(self.url, {'segmentation_method': 'rfm'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        insights = data['insights']
        
        required_fields = [
            'highest_revenue_segment',
            'largest_segment',
            'fastest_growing_segment',
            'needs_attention'
        ]
        
        for field in required_fields:
            self.assertIn(field, insights)
    
    def test_rfm_segment_structure(self):
        """Test that each segment has all required fields."""
        response = self.client.get(self.url, {'segmentation_method': 'rfm'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        self.assertGreater(len(segments), 0, "Should have at least one segment")
        
        segment = segments[0]
        required_fields = [
            'segment_name',
            'segment_code',
            'description',
            'customer_count',
            'total_revenue',
            'average_order_value',
            'recency_score',
            'frequency_score',
            'monetary_score',
            'characteristics',
            'recommended_actions'
        ]
        
        for field in required_fields:
            self.assertIn(field, segment, f"Segment missing field: {field}")
        
        # Check characteristics structure
        characteristics = segment['characteristics']
        self.assertIn('avg_days_since_last_purchase', characteristics)
        self.assertIn('avg_purchase_frequency', characteristics)
        self.assertIn('avg_total_spend', characteristics)

        # Check recommended_actions is a list
        self.assertIsInstance(segment['recommended_actions'], list)
        self.assertGreater(len(segment['recommended_actions']), 0)
    
    def test_rfm_scoring_accuracy(self):
        """Test that RFM scores are calculated correctly."""
        response = self.client.get(self.url, {'segmentation_method': 'rfm'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        # Find Champion segment (should have high scores)
        champion_segment = next(
            (s for s in segments if 'Champion' in s['segment_name']),
            None
        )
        
        if champion_segment:
            # Champions should have high R, F, M scores
            self.assertGreaterEqual(champion_segment['recency_score'], 4)
            self.assertGreaterEqual(champion_segment['frequency_score'], 4)
            self.assertGreaterEqual(champion_segment['monetary_score'], 4)
        
        # Find Hibernating segment (should have low scores)
        hibernating_segment = next(
            (s for s in segments if 'Hibernating' in s['segment_name']),
            None
        )
        
        if hibernating_segment:
            # Hibernating should have low recency
            self.assertLessEqual(hibernating_segment['recency_score'], 2)
    
    def test_customer_count_accuracy(self):
        """Test that customer counts are accurate."""
        response = self.client.get(self.url, {'segmentation_method': 'rfm'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']

        # Total customers across all segments should equal our test customers
        total_customers = sum(s['customer_count'] for s in segments)
        self.assertEqual(total_customers, 5, "Should have 5 customers total")
    
    def test_date_range_filtering(self):
        """Test filtering by date range."""
        # Last 30 days (should exclude older cohorts like hibernating)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        response = self.client.get(self.url, {
            'segmentation_method': 'rfm',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        # Should have fewer customers in 30-day window
        total_customers = sum(s['customer_count'] for s in segments)
        self.assertLess(total_customers, 5)
    
    def test_storefront_filtering(self):
        """Test filtering by storefront."""
        # Create another storefront
        other_storefront = StoreFront.objects.create(
            user=self.user,
            name='Other Store',
            location='Uptown'
        )
        
        # Create customer with sales in other storefront
        other_customer = Customer.objects.create(
            business=self.business,
            name='Other Customer',
            email='other@example.com',
            created_by=self.user
        )

        sale = Sale.objects.create(
            business=self.business,
            storefront=other_storefront,
            user=self.user,
            customer=other_customer,
            status=Sale.STATUS_COMPLETED,
            type=Sale.TYPE_RETAIL,
            payment_type=Sale.PAYMENT_TYPE_CASH,
            subtotal=Decimal('200.00'),
            total_amount=Decimal('200.00'),
            amount_paid=Decimal('200.00'),
            amount_due=Decimal('0.00'),
            amount_refunded=Decimal('0.00'),
            discount_amount=Decimal('0.00'),
            tax_amount=Decimal('0.00'),
            completed_at=timezone.now()
        )

        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=Decimal('1.00'),
            unit_price=Decimal('200.00'),
            total_price=Decimal('200.00')
        )
        
        # Filter by main storefront
        response = self.client.get(self.url, {
            'segmentation_method': 'rfm',
            'storefront_id': str(self.storefront.id)
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        # Should only include original 5 customers
        total_customers = sum(s['customer_count'] for s in segments)
        self.assertEqual(total_customers, 5)
    
    def test_segment_filtering_by_name(self):
        """Test filtering to specific segment by name."""
        response = self.client.get(self.url, {
            'segmentation_method': 'rfm',
            'segment': 'Champions'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        # Should only return Champions segment
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]['segment_name'], 'Champions')
    
    def test_segment_filtering_by_code(self):
        """Test filtering to specific segment by code."""
        response = self.client.get(self.url, {
            'segmentation_method': 'rfm',
            'segment': 'R1F1M2'  # Hibernating code
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        if segments:
            self.assertEqual(segments[0]['segment_code'], 'R1F1M2')
    
    def test_invalid_segmentation_method(self):
        """Test error handling for invalid method."""
        response = self.client.get(self.url, {
            'segmentation_method': 'invalid_method'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertIn('error', payload)
    
    def test_csv_export_format(self):
        """Test CSV export."""
        response = self.client.get(self.url, {
            'segmentation_method': 'rfm',
            'export_format': 'csv'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Check CSV content
        content = response.content.decode('utf-8')
        self.assertIn('Customer Segmentation Report', content)
        self.assertIn('Method: RFM', content)
        self.assertIn('Insights', content)
    
    def test_pdf_export_format(self):
        """Test PDF export."""
        response = self.client.get(self.url, {
            'segmentation_method': 'rfm',
            'export_format': 'pdf'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Check PDF header
        content = response.content
        self.assertTrue(content.startswith(b'%PDF'))
    
    def test_caching_behavior(self):
        """Test that results are cached."""
        # First request
        response1 = self.client.get(self.url, {'segmentation_method': 'rfm'})
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        data1 = response1.json()['data']
        
        # Second request (should be cached)
        response2 = self.client.get(self.url, {'segmentation_method': 'rfm'})
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.json()['data']
        
        # Results should be identical
        self.assertEqual(data1['segments'], data2['segments'])
    
    def test_revenue_calculations(self):
        """Test that revenue calculations are accurate."""
        response = self.client.get(self.url, {'segmentation_method': 'rfm'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        # Segments are sorted by revenue; top segment should reflect highest spenders
        self.assertGreater(len(segments), 0)
        top_segment = segments[0]

        # Highest revenue bucket should reflect the $5,000 champion cohort
        self.assertAlmostEqual(top_segment['total_revenue'], 5000.0, delta=1.0)
        self.assertAlmostEqual(top_segment['average_order_value'], 500.0, delta=1.0)
    
    def test_empty_dataset(self):
        """Test handling when no customers exist."""
        # Delete all customers
        Customer.objects.all().delete()
        
        response = self.client.get(self.url, {'segmentation_method': 'rfm'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        
        self.assertEqual(data['method'], 'rfm')
        self.assertEqual(len(data['segments']), 0)
        
        # Insights should all be None
        insights = data['insights']
        self.assertIsNone(insights['highest_revenue_segment'])
        self.assertIsNone(insights['largest_segment'])
    
    def test_authentication_required(self):
        """Test that authentication is required."""
        self.client.logout()
        response = self.client.get(self.url)

        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
        )
    
    def test_segments_sorted_by_revenue(self):
        """Test that segments are sorted by revenue descending."""
        response = self.client.get(self.url, {'segmentation_method': 'rfm'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        segments = data['segments']
        
        # Check that revenue is in descending order
        revenues = [s['total_revenue'] for s in segments]
        self.assertEqual(revenues, sorted(revenues, reverse=True))
    
    def test_value_method_placeholder(self):
        """Test that value method returns placeholder."""
        response = self.client.get(self.url, {'segmentation_method': 'value'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        
        self.assertEqual(data['method'], 'value')
        self.assertEqual(len(data['segments']), 0)
    
    def test_behavior_method_placeholder(self):
        """Test that behavior method returns placeholder."""
        response = self.client.get(self.url, {'segmentation_method': 'behavior'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        
        self.assertEqual(data['method'], 'behavior')
        self.assertEqual(len(data['segments']), 0)
