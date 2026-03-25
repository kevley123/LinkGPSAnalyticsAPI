"""
Management command: score a single real-time GPS point against the trained model.

Usage:
    python manage.py score_point --device 5 --lat 10.1234 --lon -84.5678 --speed 65
"""
from django.core.management.base import BaseCommand
from analytics.ml_pipeline import InferenceService
import json


class Command(BaseCommand):
    help = 'Score a single GPS point against the device anomaly model'

    def add_arguments(self, parser):
        parser.add_argument('--device', type=int, required=True)
        parser.add_argument('--lat', type=float, required=True)
        parser.add_argument('--lon', type=float, required=True)
        parser.add_argument('--speed', type=float, default=0)
        parser.add_argument('--heading', type=float, default=0)
        parser.add_argument('--altitude', type=float, default=0)
        parser.add_argument('--accuracy', type=float, default=0)
        parser.add_argument('--no-save', action='store_true', help="Don't persist result")

    def handle(self, *args, **options):
        result = InferenceService().score_point(
            device_id=options['device'],
            latitude=options['lat'],
            longitude=options['lon'],
            speed=options['speed'],
            heading=options['heading'],
            altitude=options['altitude'],
            accuracy=options['accuracy'],
            save=not options['no_save'],
        )
        self.stdout.write(json.dumps(result, indent=2))
        style = self.style.ERROR if result.get('is_anomaly') else self.style.SUCCESS
        self.stdout.write(style(f"\nRisk: {result.get('risk_level', '?').upper()}"))
