from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_businessinvitation_payload"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="platform_role",
            field=models.CharField(
                choices=[
                    ("NONE", "None"),
                    ("SUPER_ADMIN", "Super Admin"),
                    ("SAAS_ADMIN", "SaaS Admin"),
                    ("SAAS_STAFF", "SaaS Staff"),
                ],
                default="NONE",
                max_length=20,
            ),
        ),
    ]
