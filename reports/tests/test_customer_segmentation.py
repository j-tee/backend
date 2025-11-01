"""
Tests for Customer Segmentation Report API

Validates RFM scoring, segment classification, insights, and exports.
"""
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from sales.models import Customer, Sale, SaleItem, Payment
from inventory.models import Product, StockMovement, Storefront, Catalog
from settings.models import Business

User = get_user_model()


class CustomerSegmentationReportTestCase(TestCase):
    """Test suite for Customer Segmentation API endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create business
        self.business = Business.objects.create(
            name='Test Business',
            business_type='retail',
            currency='USD'
        )
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.business = self.business
        self.user.save()
        
        # Create storefront
        self.storefront = Storefront.objects.create(
            business=self.business,
            name='Main Store',
            location='Downtown'
        )
        
        # Create catalog
        self.catalog = Catalog.objects.create(
            business=self.business,
            name='Default Catalog'
        )
        
        # Create product
        self.product = Product.objects.create(
            business=self.business,
            catalog=self.catalog,
            sku='TEST-001',
            name='Test Product',
            price=Decimal('50.00'),
            stock_quantity=1000
        )
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.url = '/api/reports/customers/segmentation/'
        
        # Create customers with different RFM profiles
        self._create_test_customers()
    
    def _create_test_customers(self):
        """Create customers with known RFM characteristics."""
        now = timezone.now()
        
        # Champion: Recent (2 days), Frequent (10 orders), High spend ($5000)
        self.champion = Customer.objects.create(
            business=self.business,
            first_name='Champion',
            last_name='Customer',
            email='champion@example.com'
        )
        for i in range(10):
            self._create_sale(
                self.champion,
                now - timedelta(days=2 + i),
                Decimal('500.00')
            )
        
        # Loyal: Recent (10 days), Frequent (8 orders), Medium-High spend ($3200)
        self.loyal = Customer.objects.create(
            business=self.business,
            first_name='Loyal',
            last_name='Customer',
            email='loyal@example.com'
        )
        for i in range(8):
            self._create_sale(
                self.loyal,
                now - timedelta(days=10 + i),
                Decimal('400.00')
            )
        
        # At Risk: Old (60 days), Medium frequency (5 orders), Medium spend ($1500)
        self.at_risk = Customer.objects.create(
            business=self.business,
            first_name='AtRisk',
            last_name='Customer',
            email='atrisk@example.com'
        )
        for i in range(5):
            self._create_sale(
                self.at_risk,
                now - timedelta(days=60 + i * 10),
                Decimal('300.00')
            )
        
        # New Customer: Very recent (1 day), Low frequency (1 order), Low spend ($100)
        self.new_customer = Customer.objects.create(
            business=self.business,
            first_name='New',
            last_name='Customer',
            email='new@example.com'
        )
        self._create_sale(
            self.new_customer,
            now - timedelta(days=1),
            Decimal('100.00')
        )
        
        # Hibernating: Very old (120 days), Low frequency (2 orders), Low spend ($150)
        self.hibernating = Customer.objects.create(
            business=self.business,
            first_name='Hibernating',
            last_name='Customer',
            email='hibernating@example.com'
        )
        for i in range(2):
            self._create_sale(
                self.hibernating,
                now - timedelta(days=120 + i * 10),
                Decimal('75.00')
            )
    
    def _create_sale(self, customer, completed_at, total_amount):
        """Helper to create a completed sale."""
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            customer=customer,
            status=Sale.STATUS_COMPLETED,
            total_amount=total_amount,
            amount_paid=total_amount,
            amount_refunded=Decimal('0.00'),
            created_at=completed_at,
            completed_at=completed_at
        )
        
        # Add sale item
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=int(total_amount / self.product.price),
            unit_price=self.product.price,
            total_price=total_amount
        )
        
        # Add payment
        Payment.objects.create(
            sale=sale,
            payment_method='cash',
            amount=total_amount,
            created_at=completed_at
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
        # Last 30 days (should exclude hibernating customer)
        response = self.client.get(self.url, {
            'segmentation_method': 'rfm',
            'days': '30'
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
        other_storefront = Storefront.objects.create(
            business=self.business,
            name='Other Store',
            location='Uptown'
        )
        
        # Create customer with sales in other storefront
        other_customer = Customer.objects.create(
            business=self.business,
            first_name='Other',
            last_name='Customer',
            email='other@example.com'
        )
        
        sale = Sale.objects.create(
            business=self.business,
            storefront=other_storefront,
            customer=other_customer,
            status=Sale.STATUS_COMPLETED,
            total_amount=Decimal('200.00'),
            amount_paid=Decimal('200.00'),
            completed_at=timezone.now()
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
            'segment_name': 'Champions'
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
            'segment_code': 'R1F1M2'  # Hibernating code
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
        
        # Find Champion segment
        champion_segment = next(
            (s for s in segments if 'Champion' in s['segment_name']),
            None
        )
        
        if champion_segment:
            # Champion should have $5000 total revenue (10 orders × $500)
            self.assertAlmostEqual(
                champion_segment['total_revenue'],
                5000.0,
                delta=1.0
            )
            
            # Average order value should be $500
            self.assertAlmostEqual(
                champion_segment['average_order_value'],
                500.0,
                delta=1.0
            )
    
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
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
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
