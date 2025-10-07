from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Business
from .models import BusinessSettings


@receiver(post_save, sender=Business)
def create_business_settings(sender, instance, created, **kwargs):
    """
    Auto-create default settings when a new business is created.
    This ensures every business has settings available immediately.
    """
    if created:
        BusinessSettings.objects.get_or_create(
            business=instance,
            defaults={
                'regional': BusinessSettings.get_default_regional(),
                'appearance': BusinessSettings.get_default_appearance(),
                'notifications': BusinessSettings.get_default_notifications(),
                'receipt': BusinessSettings.get_default_receipt(),
            }
        )
