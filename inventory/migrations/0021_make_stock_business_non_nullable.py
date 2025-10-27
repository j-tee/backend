from django.db import migrations, models


def validate_no_null_stock_business(apps, schema_editor):
    Stock = apps.get_model('inventory', 'Stock')
    null_count = Stock.objects.filter(business__isnull=True).count()
    if null_count > 0:
        raise RuntimeError(f"Cannot make Stock.business non-nullable: {null_count} rows with NULL business_id remain")


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0020_add_stock_business'),
    ]

    operations = [
        migrations.RunPython(validate_no_null_stock_business, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='stock',
            name='business',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='stocks', to='accounts.business'),
        ),
    ]
