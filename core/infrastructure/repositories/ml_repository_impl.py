from typing import List, Optional
from core.domain.entities.ml_entities import (
    DailyRouteMl, AnomalyModelMl, RouteAnomalyMl, RouteClusterMl
)
from core.domain.ports.ml_repository import IMLRepository
from core.models import (
    DailyRouteMl as DailyRouteMlModel,
    AnomalyModelMl as AnomalyModelMlModel,
    RouteAnomalyMl as RouteAnomalyMlModel,
    RouteClusterMl as RouteClusterMlModel,
)


class MLRepositoryImpl(IMLRepository):

    # ── Daily Routes ML ──────────────────────────────────────────
    def get_daily_routes_ml(self, device_id: int, limit: int = 30) -> List[DailyRouteMl]:
        qs = DailyRouteMlModel.objects.filter(device_id=device_id).order_by('-date')[:limit]
        return [
            DailyRouteMl(
                id=m.pk, device_id=m.device_id, date=m.date,
                route=m.route, route_json=m.route_json,
                total_distance=m.total_distance, avg_speed=m.avg_speed,
                created_at=m.created_at,
            ) for m in qs
        ]

    # ── Anomaly Models ───────────────────────────────────────────
    def get_latest_model(self, device_id: int) -> Optional[AnomalyModelMl]:
        m = AnomalyModelMlModel.objects.filter(device_id=device_id).order_by('-created_at').first()
        if not m:
            return None
        return AnomalyModelMl(
            id=m.pk, device_id=m.device_id, model_path=m.model_path,
            model_type=m.model_type, trained_from=m.trained_from,
            trained_to=m.trained_to, created_at=m.created_at,
        )

    def save_anomaly_model(self, model: AnomalyModelMl) -> AnomalyModelMl:
        m = AnomalyModelMlModel.objects.create(
            device_id=model.device_id,
            model_path=model.model_path,
            model_type=model.model_type,
            trained_from=model.trained_from,
            trained_to=model.trained_to,
        )
        model.id = m.pk
        return model

    # ── Route Anomalies ──────────────────────────────────────────
    def get_anomalies_by_device(
        self, device_id: int, limit: int = 100
    ) -> List[RouteAnomalyMl]:
        qs = RouteAnomalyMlModel.objects.filter(
            device_id=device_id
        ).order_by('-detected_at')[:limit]
        return [
            RouteAnomalyMl(
                id=m.pk, device_id=m.device_id, latitude=m.latitude,
                longitude=m.longitude, geom=m.geom, anomaly_score=m.anomaly_score,
                is_anomaly=m.is_anomaly, detected_at=m.detected_at,
                metadata=m.metadata or {},
            ) for m in qs
        ]

    def save_route_anomaly(self, anomaly: RouteAnomalyMl) -> RouteAnomalyMl:
        m = RouteAnomalyMlModel.objects.create(
            device_id=anomaly.device_id,
            latitude=anomaly.latitude,
            longitude=anomaly.longitude,
            anomaly_score=anomaly.anomaly_score,
            is_anomaly=anomaly.is_anomaly,
            detected_at=anomaly.detected_at,
            metadata=anomaly.metadata,
        )
        anomaly.id = m.pk
        return anomaly

    # ── Route Clusters ───────────────────────────────────────────
    def get_clusters_by_device(self, device_id: int) -> List[RouteClusterMl]:
        qs = RouteClusterMlModel.objects.filter(device_id=device_id).order_by('cluster_id')
        return [
            RouteClusterMl(
                id=m.pk, device_id=m.device_id, cluster_id=m.cluster_id,
                centroid_lat=m.centroid_lat, centroid_lng=m.centroid_lng,
                centroid_geom=m.centroid_geom, density=m.density,
                created_at=m.created_at,
            ) for m in qs
        ]

    def save_route_cluster(self, cluster: RouteClusterMl) -> RouteClusterMl:
        m = RouteClusterMlModel.objects.create(
            device_id=cluster.device_id,
            cluster_id=cluster.cluster_id,
            centroid_lat=cluster.centroid_lat,
            centroid_lng=cluster.centroid_lng,
            density=cluster.density,
        )
        cluster.id = m.pk
        return cluster
