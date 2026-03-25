from django.urls import path
from .views import health

# ── Tracking controllers ──────────────────────────────────────────
from core.api.controllers.tracking_controller import (
    list_devices,
    get_device,
    update_device_modo,
    get_device_last_position,
    get_device_history,
    get_all_latest_positions,
    get_device_alerts,
    get_vehicle_geofences,
)

# ── ML controllers ────────────────────────────────────────────────
from core.api.controllers.ml_controller import (
    score_gps_point,
    confirm_gps_alert,
    get_anomalies,
    get_heatmap_device,
    get_global_heatmap,
    generate_global_heatmap,
    get_device_anomaly_summary,
    get_weekly_report,
    trigger_training,
    trigger_inference,
    # Legacy endpoints from initial build:
    get_daily_routes_ml,
    get_route_anomalies,
    get_route_clusters,
    get_anomaly_model_meta,
    # Model 2 — DBSCAN Cluster endpoints:
    get_vehicle_clusters,
    trigger_clustering,
    get_cluster_heatmap,
)

urlpatterns = [
    # Health
    path('health/', health),

    # Devices
    path('devices/', list_devices),
    path('devices/<int:device_id>/', get_device),
    path('devices/<int:device_id>/modo/', update_device_modo),

    # GPS Positions
    path('devices/<int:device_id>/position/', get_device_last_position),
    path('devices/<int:device_id>/history/', get_device_history),
    path('positions/latest/', get_all_latest_positions),

    # Alerts
    path('devices/<int:device_id>/alerts/', get_device_alerts),

    # Geofences
    path('geofences/vehicle/<int:vehicle_id>/', get_vehicle_geofences),

    # ── ML: Pipeline Triggers (async via Celery) ──────────────────
    path('ml/vehicles/<int:vehicle_id>/train/', trigger_training),
    path('ml/vehicles/<int:vehicle_id>/infer/', trigger_inference),

    # ── ML: Real-time scoring ──────────────────────────────────────
    path('ml/vehicles/<int:vehicle_id>/score/', score_gps_point),
    path('ml/vehicles/<int:vehicle_id>/confirm/', confirm_gps_alert),

    # ── ML: Anomaly results ────────────────────────────────────────
    path('ml/vehicles/<int:vehicle_id>/anomalies/', get_anomalies),
    path('ml/vehicles/<int:vehicle_id>/summary/', get_device_anomaly_summary),
    path('ml/vehicles/<int:vehicle_id>/weekly-report/', get_weekly_report),
    path('ml/vehicles/<int:vehicle_id>/model/', get_anomaly_model_meta),

    # ── ML: Heatmap data ──────────────────────────────────────────
    path('ml/vehicles/<int:vehicle_id>/heatmap/', get_heatmap_device),
    path('ml/heatmap/all/', get_global_heatmap),
    path('ml/heatmap/generate/', generate_global_heatmap),

    # ── ML: Supplementary ─────────────────────────────────────────
    path('ml/vehicles/<int:vehicle_id>/daily-routes/', get_daily_routes_ml),
    path('ml/vehicles/<int:vehicle_id>/route-anomalies/', get_route_anomalies),

    # ── ML: Clusters (Model 2 — DBSCAN) ───────────────────────────
    path('ml/vehicles/<int:vehicle_id>/clusters/', get_vehicle_clusters),
    path('ml/vehicles/<int:vehicle_id>/cluster/run/', trigger_clustering),
    path('ml/vehicles/<int:vehicle_id>/cluster-heatmap/', get_cluster_heatmap),
]
