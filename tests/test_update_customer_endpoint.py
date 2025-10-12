"""
Test suite for the update_customer endpoint on Sales
Tests the critical POS functionality of updating customer on DRAFT sales
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from sales.models import Sale, Customer, SaleItem, AuditLog
from inventory.models import Product, StockProduct, StoreFront, Category
from accounts.models import Business, BusinessMembership

User = get_user_model()


class UpdateCustomerEndpointTest(TestCase):
    """Test the update_customer endpoint"""
    
    def setUp(self):
        """Set up test data"""
        # Create owner user
        self.owner = User.objects.create_user(
            email="owner@test.com",
            password="testpass123",
            name="Test Owner"
        )
        
        # Create business
        self.business = Business.objects.create(
            name="Test Business",
            tin="123456789",
            email="test@business.com",
            address="123 Test St",
            owner=self.owner
        )
        
        # Create user and membership
        self.user = User.objects.create_user(
            email="testuser@test.com",
            password="testpass123",
            name="Test User"
        )
        
        self.membership = BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.STAFF,
            is_admin=True,
            is_active=True
        )
        
        # Create storefront
        self.storefront = StoreFront.objects.create(
            user=self.owner,
            name="Test Store",
            location="Test Location"
        )
        
        # Create customers
        self.walk_in_customer = Customer.objects.create(
            business=self.business,
            name="Walk-in Customer",
            customer_type='WALK_IN'
        )
        
        self.fred = Customer.objects.create(
            business=self.business,
            name="Fred Amugi",
            phone="4575467457646S",
            customer_type='WHOLESALE'
        )
        
        self.jane = Customer.objects.create(
            business=self.business,
            name="Jane Doe",
            email="jane@example.com",
            customer_type='RETAIL'
        )
        
        # Create customer from different business
        self.other_owner = User.objects.create_user(
            email="otherowner@test.com",
            password="testpass123",
            name="Other Owner"
        )
        
        self.other_business = Business.objects.create(
            name="Other Business",
            tin="987654321",
            email="other@business.com",
            address="456 Other St",
            owner=self.other_owner
        )
        
        self.other_customer = Customer.objects.create(
            business=self.other_business,
            name="Other Customer",
            customer_type='RETAIL'
        )
    
    def test_update_customer_on_draft_sale_success(self):
        """Should successfully update customer on DRAFT sale"""
        print("\n" + "="*80)
        print("TEST: Update customer on DRAFT sale - SUCCESS CASE")
        print("="*80)
        
        # Create DRAFT sale with walk-in customer
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.walk_in_customer,
            type='WHOLESALE',
            status='DRAFT'
        )
        
        print(f"✅ Created DRAFT sale: {sale.id}")
        print(f"   Initial customer: {sale.customer.name}")
        
        # Simulate API call to update customer
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        # Update customer to Fred
        url = f'/sales/api/sales/{sale.id}/update_customer/'
        response = client.patch(url, {'customer': str(self.fred.id)}, format='json')
        
        print(f"\n📡 API Request:")
        print(f"   PATCH {url}")
        print(f"   Body: {{'customer': '{self.fred.id}'}}")
        
        print(f"\n📨 API Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Data: {response.json()}")
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['new_customer'], 'Fred Amugi')
        
        # Verify database updated
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.fred)
        
        print(f"\n✅ Customer successfully updated:")
        print(f"   From: Walk-in Customer")
        print(f"   To: {sale.customer.name}")
        
        # Verify audit log created
        audit_log = AuditLog.objects.filter(sale=sale, event_type='sale.customer_updated').first()
        self.assertIsNotNone(audit_log)
        print(f"\n📝 Audit log created: {audit_log.description}")
        
        print("\n✅ TEST PASSED: Customer update successful")
    
    def test_update_customer_on_completed_sale_fails(self):
        """Should reject customer update on COMPLETED sale"""
        print("\n" + "="*80)
        print("TEST: Update customer on COMPLETED sale - SHOULD FAIL")
        print("="*80)
        
        # Create COMPLETED sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.walk_in_customer,
            type='RETAIL',
            status='COMPLETED',
            total_amount=Decimal('100.00'),
            amount_paid=Decimal('100.00')
        )
        
        print(f"✅ Created COMPLETED sale: {sale.id}")
        print(f"   Status: {sale.status}")
        print(f"   Customer: {sale.customer.name}")
        
        # Try to update customer
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        url = f'/sales/api/sales/{sale.id}/update_customer/'
        response = client.patch(url, {'customer': str(self.fred.id)}, format='json')
        
        print(f"\n📡 Attempted API Request:")
        print(f"   PATCH {url}")
        print(f"   Body: {{'customer': '{self.fred.id}'}}")
        
        print(f"\n📨 API Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.json().get('error')}")
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        self.assertIn('not in DRAFT status', response.json()['error'])
        
        # Verify customer NOT updated
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.walk_in_customer)
        
        print(f"\n✅ Security check passed: Cannot update completed sale")
        print(f"   Customer remains: {sale.customer.name}")
        print("\n✅ TEST PASSED: Completed sale protection working")
    
    def test_update_customer_wrong_business_fails(self):
        """Should reject customer from different business"""
        print("\n" + "="*80)
        print("TEST: Update with customer from different business - SHOULD FAIL")
        print("="*80)
        
        # Create DRAFT sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.walk_in_customer,
            type='RETAIL',
            status='DRAFT'
        )
        
        print(f"✅ Created DRAFT sale: {sale.id}")
        print(f"   Business: {sale.business.name}")
        print(f"   Customer: {sale.customer.name}")
        
        # Try to update with customer from different business
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        url = f'/sales/api/sales/{sale.id}/update_customer/'
        response = client.patch(url, {'customer': str(self.other_customer.id)}, format='json')
        
        print(f"\n📡 Attempted API Request:")
        print(f"   PATCH {url}")
        print(f"   Body: {{'customer': '{self.other_customer.id}'}}")
        print(f"   Attempting to use customer from: {self.other_business.name}")
        
        print(f"\n📨 API Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.json().get('error')}")
        
        # Assertions
        self.assertEqual(response.status_code, 404)
        self.assertIn('not found', response.json()['error'].lower())
        
        # Verify customer NOT updated
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.walk_in_customer)
        
        print(f"\n✅ Business boundary check passed")
        print(f"   Customer remains: {sale.customer.name}")
        print("\n✅ TEST PASSED: Cross-business protection working")
    
    def test_update_customer_nonexistent_fails(self):
        """Should reject invalid customer UUID"""
        print("\n" + "="*80)
        print("TEST: Update with non-existent customer UUID - SHOULD FAIL")
        print("="*80)
        
        # Create DRAFT sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.walk_in_customer,
            type='RETAIL',
            status='DRAFT'
        )
        
        print(f"✅ Created DRAFT sale: {sale.id}")
        
        # Try to update with non-existent UUID
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        import uuid
        
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        fake_uuid = str(uuid.uuid4())
        url = f'/sales/api/sales/{sale.id}/update_customer/'
        response = client.patch(url, {'customer': fake_uuid}, format='json')
        
        print(f"\n📡 Attempted API Request:")
        print(f"   PATCH {url}")
        print(f"   Body: {{'customer': '{fake_uuid}'}}")
        print(f"   (Non-existent UUID)")
        
        print(f"\n📨 API Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.json().get('error')}")
        
        # Assertions
        self.assertEqual(response.status_code, 404)
        
        # Verify customer NOT updated
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.walk_in_customer)
        
        print(f"\n✅ UUID validation passed")
        print(f"   Customer remains: {sale.customer.name}")
        print("\n✅ TEST PASSED: Invalid UUID protection working")
    
    def test_update_customer_missing_field_fails(self):
        """Should reject request without customer field"""
        print("\n" + "="*80)
        print("TEST: Update without customer field - SHOULD FAIL")
        print("="*80)
        
        # Create DRAFT sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.walk_in_customer,
            type='RETAIL',
            status='DRAFT'
        )
        
        print(f"✅ Created DRAFT sale: {sale.id}")
        
        # Try to update without customer field
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        url = f'/sales/api/sales/{sale.id}/update_customer/'
        response = client.patch(url, {}, format='json')
        
        print(f"\n📡 Attempted API Request:")
        print(f"   PATCH {url}")
        print(f"   Body: {{}} (empty)")
        
        print(f"\n📨 API Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.json().get('error')}")
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        self.assertIn('required', response.json()['error'].lower())
        
        print(f"\n✅ Required field validation passed")
        print("\n✅ TEST PASSED: Missing field protection working")
    
    def test_update_customer_preserves_other_fields(self):
        """Should only update customer, not other fields"""
        print("\n" + "="*80)
        print("TEST: Customer update preserves other sale fields")
        print("="*80)
        
        # Create DRAFT sale with data (no items for simplicity)
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.walk_in_customer,
            type='WHOLESALE',
            status='DRAFT',
            notes="Important sale notes",
            discount_amount=Decimal('5.00')
        )
        
        print(f"✅ Created DRAFT sale with data:")
        print(f"   Customer: {sale.customer.name}")
        print(f"   Type: {sale.type}")
        print(f"   Notes: {sale.notes}")
        print(f"   Discount: GH₵ {sale.discount_amount}")
        
        # Update customer
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        url = f'/sales/api/sales/{sale.id}/update_customer/'
        response = client.patch(url, {'customer': str(self.fred.id)}, format='json')
        
        print(f"\n📡 Updating customer to: {self.fred.name}")
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        
        # Verify only customer changed
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.fred)
        self.assertEqual(sale.type, 'WHOLESALE')
        self.assertEqual(sale.status, 'DRAFT')
        self.assertEqual(sale.notes, "Important sale notes")
        self.assertEqual(sale.discount_amount, Decimal('5.00'))
        
        print(f"\n✅ Verification after update:")
        print(f"   Customer: {sale.customer.name} ✅ CHANGED")
        print(f"   Type: {sale.type} ✅ UNCHANGED")
        print(f"   Notes: {sale.notes} ✅ UNCHANGED")
        print(f"   Discount: GH₵ {sale.discount_amount} ✅ UNCHANGED")
        
        print("\n✅ TEST PASSED: Only customer updated, other fields preserved")
    
    def test_pos_customer_selection_flow(self):
        """Integration test: Complete POS customer selection flow"""
        print("\n" + "="*80)
        print("INTEGRATION TEST: Complete POS Customer Selection Flow")
        print("="*80)
        
        # Simulate POS workflow
        print("\n📱 Simulating POS Workflow:")
        print("1. User opens POS → Backend creates DRAFT sale")
        
        # Step 1: Create DRAFT sale (happens automatically)
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.walk_in_customer,
            type='WHOLESALE',
            status='DRAFT'
        )
        
        print(f"   ✅ DRAFT sale created: {sale.id}")
        print(f"   ✅ Initial customer: {sale.customer.name}")
        
        # Step 2: User selects customer from dropdown
        print("\n2. User selects 'Fred Amugi' from dropdown")
        
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        url = f'/sales/api/sales/{sale.id}/update_customer/'
        response = client.patch(url, {'customer': str(self.fred.id)}, format='json')
        
        self.assertEqual(response.status_code, 200)
        print(f"   ✅ Customer updated via API")
        
        # Step 3: Verify customer persisted
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.fred)
        print(f"   ✅ Customer verified: {sale.customer.name}")
        
        # Step 4: Complete payment
        print("\n3. User completes payment")
        
        sale.status = 'COMPLETED'
        sale.total_amount = Decimal('800.00')
        sale.amount_paid = Decimal('800.00')
        sale.payment_type = 'CASH'
        sale.save()
        
        print(f"   ✅ Sale completed")
        print(f"   ✅ Total: GH₵ {sale.total_amount}")
        
        # Step 5: Verify customer persists in completed sale
        print("\n4. Verifying customer persists in completed sale...")
        
        sale.refresh_from_db()
        self.assertEqual(sale.customer, self.fred)
        self.assertEqual(sale.status, 'COMPLETED')
        
        print(f"   ✅ Customer in completed sale: {sale.customer.name}")
        
        print("\n" + "="*80)
        print("✅ INTEGRATION TEST PASSED: Complete POS flow working correctly!")
        print("   Customer selection persists from DRAFT → COMPLETED")
        print("="*80)


def run_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 RUNNING UPDATE_CUSTOMER ENDPOINT TESTS")
    print("="*80)
    
    import unittest
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(UpdateCustomerEndpointTest)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
        print("\n🎯 The update_customer endpoint is working correctly:")
        print("   ✅ Updates customer on DRAFT sales")
        print("   ✅ Rejects updates on completed sales")
        print("   ✅ Validates business boundaries")
        print("   ✅ Validates customer existence")
        print("   ✅ Requires customer field")
        print("   ✅ Preserves other sale data")
        print("   ✅ Complete POS flow working")
        print("\n🚀 Ready for frontend integration!")
    else:
        print("\n❌ SOME TESTS FAILED")
        print("   Review the errors above and fix issues")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
