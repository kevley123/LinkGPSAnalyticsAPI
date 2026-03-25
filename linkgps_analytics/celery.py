"""
Celery application setup for linkgps_analytics.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'linkgps_analytics.settings')

app = Celery('linkgps_analytics')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
