"""
Management command: run the full ML pipeline for one device or all devices.

Usage:
    # Aggregate + train + infer for device 5 (last 20 days)
    python manage.py ml_pipeline --device 5

    # Train all active devices
    python manage.py ml_pipeline --all

    # Only aggregate (no training)
    python manage.py ml_pipeline --device 5 --step aggregate

    # Only infer with last 48h
    python manage.py ml_pipeline --device 5 --step infer --hours 48
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from analytics.ml_pipeline import AggregationService, TrainingService, InferenceService
from core.models import TrackedDevice

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run ML anomaly detection pipeline (aggregate | train | infer | all)'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--device', type=int, help='Run pipeline for a specific device ID')
        group.add_argument('--all', action='store_true', help='Run pipeline for all active devices')

        parser.add_argument(
            '--step',
            choices=['aggregate', 'train', 'infer', 'full'],
            default='full',
            help='Which step to run (default: full)'
        )
        parser.add_argument('--days', type=int, default=20, help='Days of history to use')
        parser.add_argument('--hours', type=int, default=24, help='Hours window for inference')

    def handle(self, *args, **options):
        step = options['step']
        days = options['days']
        hours = options['hours']

        if options['all']:
            device_ids = list(TrackedDevice.objects.values_list('id', flat=True))
            self.stdout.write(f"[ml_pipeline] Running '{step}' for {len(device_ids)} devices...")
        else:
            device_ids = [options['device']]

        for device_id in device_ids:
            self.stdout.write(f"  → Device {device_id}")
            try:
                self._run_for_device(device_id, step, days, hours)
            except Exception as e:
                self.stderr.write(f"    ERROR: {e}")
                logger.exception(f"Pipeline failed for device {device_id}")

        self.stdout.write(self.style.SUCCESS(f"\n✓ Pipeline '{step}' complete."))

    def _run_for_device(self, device_id: int, step: str, days: int, hours: int):
        agg = AggregationService()
        trainer = TrainingService()
        infer = InferenceService()

        if step in ('aggregate', 'full'):
            self.stdout.write(f"    [aggregate] last {days} days...")
            pks = agg.aggregate_device_last_n_days(device_id, days)
            self.stdout.write(f"    [aggregate] {len(pks)} daily records saved")

        if step in ('train', 'full'):
            self.stdout.write(f"    [train] IsolationForest...")
            path = trainer.train_device(device_id, days)
            if path:
                self.stdout.write(f"    [train] model saved → {path}")
            else:
                self.stdout.write("    [train] SKIPPED (not enough data)")

        if step in ('infer', 'full'):
            self.stdout.write(f"    [infer] last {hours}h...")
            results = infer.score_device_recent(device_id, hours)
            anomalies = sum(1 for r in results if r['is_anomaly'])
            self.stdout.write(
                f"    [infer] {len(results)} points scored, {anomalies} anomalies"
            )
