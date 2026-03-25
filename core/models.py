from django.db import models


# ────────────────────────────────────────────────────────────────
# Core tracking tables (managed = False — already exist in DB)
# ────────────────────────────────────────────────────────────────

class TrackedDevice(models.Model):
    device_imei = models.CharField(max_length=20, unique=True)
    vehicle_id = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)
    modo = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'tracked_devices'
        app_label = 'core'

    def __str__(self):
        return f"Device {self.device_imei} (id={self.pk})"


class GpsPosition(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING,
        db_column='device_id', related_name='positions'
    )
    # geom is kept as a generic field or ignored in ORM since we use raw SQL with ST_X/ST_Y
    # geom = models.TextField(null=True, blank=True) 
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    satellites = models.IntegerField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField()
    metadata = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        managed = False
        db_table = 'gps_positions'
        app_label = 'core'
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Position device={self.device_id} at {self.recorded_at}"


class DeviceStatus(models.Model):
    device = models.OneToOneField(
        TrackedDevice, on_delete=models.DO_NOTHING,
        primary_key=True, db_column='device_id', related_name='status_record'
    )
    ignition = models.BooleanField(null=True, blank=True)
    battery_level = models.FloatField(null=True, blank=True)
    gsm_signal = models.IntegerField(null=True, blank=True)
    gps_fix = models.BooleanField(null=True, blank=True)
    last_connection = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        managed = False
        db_table = 'device_status'
        app_label = 'core'


class Geofence(models.Model):
    vehicle_id = models.BigIntegerField(null=True, blank=True)
    name = models.CharField(max_length=120, null=True, blank=True)
    # geom = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    type = models.CharField(max_length=10, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'geofences'
        app_label = 'core'

    def __str__(self):
        return f"Geofence '{self.name}' (vehicle={self.vehicle_id})"


class GeofenceEvent(models.Model):
    geofence = models.ForeignKey(
        Geofence, on_delete=models.DO_NOTHING, db_column='geofence_id'
    )
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    position_id = models.BigIntegerField(null=True, blank=True)
    event_type = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        managed = False
        db_table = 'geofence_events'
        app_label = 'core'


class DeviceEvent(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    event_type = models.CharField(max_length=50, null=True, blank=True)
    position_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        managed = False
        db_table = 'device_events'
        app_label = 'core'


class Alert(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    alert_type = models.CharField(max_length=50, null=True, blank=True)
    severity = models.CharField(max_length=20, null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)
    created_at = models.DateTimeField(null=True, blank=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'alerts'
        app_label = 'core'


class DailyRoute(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    route_date = models.DateField(null=True, blank=True)
    # route_geom = models.TextField(null=True, blank=True) 
    distance_km = models.FloatField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'daily_routes'
        app_label = 'core'


class RiskZone(models.Model):
    name = models.TextField(null=True, blank=True)
    # geom = models.TextField(null=True, blank=True)
    risk_level = models.FloatField(null=True, blank=True)
    source = models.TextField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    votes_up = models.IntegerField(default=0)
    votes_down = models.IntegerField(default=0)
    reports = models.IntegerField(default=0)
    created_by = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'risk_zones'  # Postgres handles search_path
        app_label = 'core'


# ────────────────────────────────────────────────────────────────
# ML Tables (managed = False — already exist in DB)
# ────────────────────────────────────────────────────────────────

class DailyRouteMl(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    date = models.DateField(null=True, blank=True)
    # route = models.TextField(null=True, blank=True)
    route_json = models.JSONField(null=True, blank=True)
    total_distance = models.FloatField(null=True, blank=True)
    avg_speed = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'daily_routes_ml'
        app_label = 'core'


class AnomalyModelMl(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    model_path = models.CharField(max_length=255, null=True, blank=True)
    model_type = models.CharField(max_length=50, null=True, blank=True)
    trained_from = models.DateField(null=True, blank=True)
    trained_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'anomaly_models_ml'
        app_label = 'core'


class RouteAnomalyMl(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    # geom = models.TextField(null=True, blank=True)
    anomaly_score = models.FloatField(null=True, blank=True)
    is_anomaly = models.BooleanField(default=False)
    detected_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        managed = False
        db_table = 'route_anomalies_ml'
        app_label = 'core'


class RouteClusterMl(models.Model):
    device = models.ForeignKey(
        TrackedDevice, on_delete=models.DO_NOTHING, db_column='device_id'
    )
    cluster_id = models.IntegerField(null=True, blank=True)
    centroid_lat = models.FloatField(null=True, blank=True)
    centroid_lng = models.FloatField(null=True, blank=True)
    density = models.FloatField(null=True, blank=True)
    # Extended fields for DBSCAN postprocessing
    radius = models.FloatField(null=True, blank=True)           # max distance to centroid in meters
    point_count = models.IntegerField(null=True, blank=True)    # number of GPS points in cluster
    label = models.CharField(max_length=20, null=True, blank=True)  # 'main' | 'secondary'
    updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'route_clusters_ml'
        app_label = 'core'
