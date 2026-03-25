"""
Celery tasks for the ML anomaly detection pipeline.
Triggered via API or on a schedule via celery-beat.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def aggregate_device_day_task(self, device_id: int, date_str: str):
    """
    Aggregate GPS positions for one device on one day.
    date_str format: 'YYYY-MM-DD'
    """
    try:
        from datetime import date
        from analytics.ml_pipeline import AggregationService
        target_date = date.fromisoformat(date_str)
        pk = AggregationService().aggregate_device_day(device_id, target_date)
        return {'status': 'ok', 'daily_route_ml_id': pk}
    except Exception as exc:
        logger.error(f"[task:aggregate] device={device_id} date={date_str} error={exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def aggregate_device_history_task(self, device_id: int, days: int = 20):
    """Aggregate last N days for a device — used before training."""
    try:
        from analytics.ml_pipeline import AggregationService
        pks = AggregationService().aggregate_device_last_n_days(device_id, days)
        return {'status': 'ok', 'days_aggregated': len(pks), 'ids': pks}
    except Exception as exc:
        logger.error(f"[task:aggregate_history] device={device_id} error={exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def train_device_model_task(self, device_id: int, days: int = 20):
    """
    Train/retrain the IsolationForest model for a device.
    Aggregates data first if needed, then trains.
    """
    try:
        from analytics.ml_pipeline import AggregationService, TrainingService

        # Step 1: ensure aggregated data exists
        AggregationService().aggregate_device_last_n_days(device_id, days)

        # Step 2: train
        model_path = TrainingService().train_device(device_id, days)
        return {
            'status': 'ok' if model_path else 'skipped',
            'device_id': device_id,
            'model_path': model_path,
        }
    except Exception as exc:
        logger.error(f"[task:train] device={device_id} error={exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def run_inference_task(self, device_id: int, hours: int = 24):
    """Batch inference: score last N hours of GPS positions for a device."""
    try:
        from analytics.ml_pipeline import InferenceService
        results = InferenceService().score_device_recent(device_id, hours)
        anomaly_count = sum(1 for r in results if r['is_anomaly'])
        return {
            'status': 'ok',
            'device_id': device_id,
            'points_scored': len(results),
            'anomalies': anomaly_count,
        }
    except Exception as exc:
        logger.error(f"[task:inference] device={device_id} error={exc}")
        raise self.retry(exc=exc)


@shared_task
def train_all_devices_task(days: int = 20):
    """Nightly job: train models for all active devices."""
    from analytics.ml_pipeline import AggregationService, TrainingService
    from core.models import TrackedDevice

    devices = TrackedDevice.objects.filter(status='active').values_list('id', flat=True)
    for device_id in devices:
        try:
            AggregationService().aggregate_device_last_n_days(device_id, days)
            TrainingService().train_device(device_id, days)
            run_inference_task.delay(device_id, hours=24)
        except Exception as e:
            logger.error(f"[task:train_all] device={device_id} error={e}")

    return {'status': 'ok', 'devices_processed': len(devices)}
