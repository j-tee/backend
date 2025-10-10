# Generated migration for adding database-level stock integrity constraints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),  # Update this to your latest migration
    ]

    operations = [
        # Add CHECK constraint: StockProduct.quantity >= 0
        migrations.AddConstraint(
            model_name='stockproduct',
            constraint=models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='stock_product_quantity_non_negative',
                violation_error_message='Stock product quantity cannot be negative'
            ),
        ),
        
        # Add CHECK constraint: StoreFrontInventory.quantity >= 0
        migrations.AddConstraint(
            model_name='storefrontinventory',
            constraint=models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='storefront_inventory_quantity_non_negative',
                violation_error_message='Storefront inventory quantity cannot be negative'
            ),
        ),
        
        # Add UNIQUE constraint: Prevent duplicate storefront inventory entries
        migrations.AddConstraint(
            model_name='storefrontinventory',
            constraint=models.UniqueConstraint(
                fields=['storefront', 'product'],
                name='unique_storefront_product',
                violation_error_message='This product already exists in this storefront inventory'
            ),
        ),
    ]
