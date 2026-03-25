"""
Application use cases — ML domain
"""
from typing import Optional, List

from core.domain.ports.ml_repository import IMLRepository
from core.domain.entities.ml_entities import (
    DailyRouteMl, AnomalyModelMl, RouteAnomalyMl, RouteClusterMl
)
from core.infrastructure.repositories.ml_repository_impl import MLRepositoryImpl


class GetDailyRoutesMl:
    def __init__(self, repo: IMLRepository = None):
        self.repo = repo or MLRepositoryImpl()

    def execute(self, device_id: int, limit: int = 30) -> List[DailyRouteMl]:
        return self.repo.get_daily_routes_ml(device_id, limit)


class GetRouteAnomalies:
    def __init__(self, repo: IMLRepository = None):
        self.repo = repo or MLRepositoryImpl()

    def execute(self, device_id: int, limit: int = 100) -> List[RouteAnomalyMl]:
        return self.repo.get_anomalies_by_device(device_id, limit)


class GetRouteClusters:
    def __init__(self, repo: IMLRepository = None):
        self.repo = repo or MLRepositoryImpl()

    def execute(self, device_id: int) -> List[RouteClusterMl]:
        return self.repo.get_clusters_by_device(device_id)


class GetLatestAnomalyModel:
    def __init__(self, repo: IMLRepository = None):
        self.repo = repo or MLRepositoryImpl()

    def execute(self, device_id: int) -> Optional[AnomalyModelMl]:
        return self.repo.get_latest_model(device_id)


class SaveRouteAnomaly:
    def __init__(self, repo: IMLRepository = None):
        self.repo = repo or MLRepositoryImpl()

    def execute(self, anomaly: RouteAnomalyMl) -> RouteAnomalyMl:
        return self.repo.save_route_anomaly(anomaly)
