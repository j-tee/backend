from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_passwordresettoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessinvitation",
            name="payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="businessinvitation",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("ACCEPTED", "Accepted"),
                    ("EXPIRED", "Expired"),
                    ("REVOKED", "Revoked"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
