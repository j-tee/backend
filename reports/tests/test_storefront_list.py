from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Business, BusinessMembership
from inventory.models import BusinessStoreFront, StoreFront
from django.contrib.auth import get_user_model


User = get_user_model()


class ReportStorefrontListViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reports@example.com",
            password="securepass123",
            name="Reports Owner",
        )

        self.business = Business.objects.create(
            owner=self.user,
            name="Reports Biz",
            tin="TIN-654321",
            email="reportsbiz@example.com",
            address="42 Analytics Road",
        )

        BusinessMembership.objects.get_or_create(
            business=self.business,
            user=self.user,
            defaults={
                'role': BusinessMembership.OWNER,
                'is_admin': True,
                'is_active': True,
            },
        )

        self.primary_storefront = StoreFront.objects.create(
            user=self.user,
            name="Flagship Store",
            location="Accra",
        )
        self.secondary_storefront = StoreFront.objects.create(
            user=self.user,
            name="Annex Store",
            location="Tema",
        )

        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.primary_storefront,
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.secondary_storefront,
        )

        self.client.force_authenticate(self.user)

    def test_lists_storefronts_for_business(self):
        url = reverse('report-storefronts')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

        storefront_ids = {entry['id'] for entry in response.data['data']}
        self.assertSetEqual(
            storefront_ids,
            {str(self.primary_storefront.id), str(self.secondary_storefront.id)}
        )

        metadata = response.data['metadata']
        self.assertEqual(metadata['count'], 2)
        self.assertIn('generated_at', metadata)
