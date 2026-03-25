from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.entities.ml_entities import (
    DailyRouteMl, AnomalyModelMl, RouteAnomalyMl, RouteClusterMl
)


class IMLRepository(ABC):

    # --- Daily Routes ML ---
    @abstractmethod
    def get_daily_routes_ml(self, device_id: int, limit: int = 30) -> List[DailyRouteMl]:
        pass

    # --- Anomaly Models ---
    @abstractmethod
    def get_latest_model(self, device_id: int) -> Optional[AnomalyModelMl]:
        pass

    @abstractmethod
    def save_anomaly_model(self, model: AnomalyModelMl) -> AnomalyModelMl:
        pass

    # --- Route Anomalies (inference results) ---
    @abstractmethod
    def get_anomalies_by_device(self, device_id: int, limit: int = 100) -> List[RouteAnomalyMl]:
        pass

    @abstractmethod
    def save_route_anomaly(self, anomaly: RouteAnomalyMl) -> RouteAnomalyMl:
        pass

    # --- Route Clusters ---
    @abstractmethod
    def get_clusters_by_device(self, device_id: int) -> List[RouteClusterMl]:
        pass

    @abstractmethod
    def save_route_cluster(self, cluster: RouteClusterMl) -> RouteClusterMl:
        pass
