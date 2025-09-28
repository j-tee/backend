import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

app = Celery('pos_backend')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Optional configuration, see the application user guide.
app.conf.update(
    task_track_started=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    result_backend='redis://localhost:6379/0',
    broker_url='redis://localhost:6379/0',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'accounts.tasks.*': {'queue': 'accounts'},
        'inventory.tasks.*': {'queue': 'inventory'},
        'sales.tasks.*': {'queue': 'sales'},
        'subscriptions.tasks.*': {'queue': 'subscriptions'},
    },
    
    # Periodic tasks
    beat_schedule={
        'cleanup-inactive-users': {
            'task': 'accounts.tasks.cleanup_inactive_users',
            'schedule': 86400.0,  # Run daily (24 hours)
        },
        'generate-user-activity-report': {
            'task': 'accounts.tasks.generate_user_activity_report',
            'schedule': 604800.0,  # Run weekly (7 days)
        },
        'check-subscription-renewals': {
            'task': 'accounts.tasks.check_subscription_renewals',
            'schedule': 3600.0,  # Run hourly
        },
        'check-stock-alerts': {
            'task': 'inventory.tasks.check_stock_levels',
            'schedule': 1800.0,  # Run every 30 minutes
        },
    },
)


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')