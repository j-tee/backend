# Generated migration for user preferences and 2FA fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_roletemplate_userrole_alter_role_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='profile_picture',
            field=models.ImageField(
                upload_to='profile_pictures/',
                null=True,
                blank=True,
                help_text='User profile picture'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='language',
            field=models.CharField(
                max_length=10,
                default='en',
                choices=[('en', 'English'), ('fr', 'French'), ('es', 'Spanish')],
                help_text='Preferred language'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='timezone',
            field=models.CharField(
                max_length=50,
                default='Africa/Accra',
                help_text='User timezone'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='date_format',
            field=models.CharField(
                max_length=20,
                default='DD/MM/YYYY',
                choices=[
                    ('DD/MM/YYYY', 'DD/MM/YYYY'),
                    ('MM/DD/YYYY', 'MM/DD/YYYY'),
                    ('YYYY-MM-DD', 'YYYY-MM-DD'),
                ],
                help_text='Preferred date format'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='time_format',
            field=models.CharField(
                max_length=10,
                default='24h',
                choices=[('12h', '12 Hour'), ('24h', '24 Hour')],
                help_text='Preferred time format'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='currency',
            field=models.CharField(
                max_length=3,
                default='GHS',
                help_text='Preferred currency code'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='preferences',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Additional user preferences'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='notification_settings',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='User notification settings'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='two_factor_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Whether 2FA is enabled'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='two_factor_secret',
            field=models.CharField(
                max_length=32,
                null=True,
                blank=True,
                help_text='TOTP secret for 2FA'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='backup_codes',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text='2FA backup codes'
            ),
        ),
    ]
