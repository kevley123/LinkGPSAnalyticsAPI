"""
Application use cases — Tracking domain
Each use case orchestrates one business operation using the ports.
"""
from typing import Optional, List
from datetime import datetime, date

from core.domain.ports.tracked_device_repository import ITrackedDeviceRepository
from core.domain.ports.gps_position_repository import IGpsPositionRepository
from core.domain.ports.device_status_repository import IDeviceStatusRepository
from core.domain.ports.alert_repository import IAlertRepository
from core.domain.ports.daily_route_repository import IDailyRouteRepository
from core.domain.ports.geofence_repository import IGeofenceRepository
from core.domain.entities.tracked_device import TrackedDevice
from core.domain.entities.gps_position import GpsPosition
from core.domain.entities.device_status import DeviceStatus
from core.domain.entities.alert import Alert
from core.domain.entities.daily_route import DailyRoute
from core.domain.entities.geofence import Geofence

from core.infrastructure.repositories.tracked_device_repository_impl import TrackedDeviceRepositoryImpl
from core.infrastructure.repositories.gps_position_repository_impl import GpsPositionRepositoryImpl
from core.infrastructure.repositories.alert_repository_impl import AlertRepositoryImpl
from core.infrastructure.repositories.geofence_repository_impl import GeofenceRepositoryImpl


# ── Device Info ──────────────────────────────────────────────────

class GetDeviceById:
    def __init__(self, repo: ITrackedDeviceRepository = None):
        self.repo = repo or TrackedDeviceRepositoryImpl()

    def execute(self, device_id: int) -> Optional[TrackedDevice]:
        return self.repo.get_by_id(device_id)


class ListAllDevices:
    def __init__(self, repo: ITrackedDeviceRepository = None):
        self.repo = repo or TrackedDeviceRepositoryImpl()

    def execute(self) -> List[TrackedDevice]:
        return self.repo.list_all()


class UpdateDeviceModo:
    def __init__(self, repo: ITrackedDeviceRepository = None):
        self.repo = repo or TrackedDeviceRepositoryImpl()

    def execute(self, device_id: int, modo: int) -> bool:
        return self.repo.update_modo(device_id, modo)


# ── GPS Positions ─────────────────────────────────────────────────

class GetDeviceLastPosition:
    def __init__(self, repo: IGpsPositionRepository = None):
        self.repo = repo or GpsPositionRepositoryImpl()

    def execute(self, device_id: int) -> Optional[GpsPosition]:
        return self.repo.get_last_by_device(device_id)


class GetDeviceHistory:
    def __init__(self, repo: IGpsPositionRepository = None):
        self.repo = repo or GpsPositionRepositoryImpl()

    def execute(
        self, device_id: int, from_dt: datetime, to_dt: datetime
    ) -> List[GpsPosition]:
        return self.repo.get_range_by_device(device_id, from_dt, to_dt)


class GetLatestAllPositions:
    def __init__(self, repo: IGpsPositionRepository = None):
        self.repo = repo or GpsPositionRepositoryImpl()

    def execute(self, limit: int = 100) -> List[GpsPosition]:
        return self.repo.get_latest_positions(limit)


# ── Alerts ────────────────────────────────────────────────────────

class GetDeviceAlerts:
    def __init__(self, repo: IAlertRepository = None):
        self.repo = repo or AlertRepositoryImpl()

    def execute(self, device_id: int, limit: int = 50) -> List[Alert]:
        return self.repo.get_by_device(device_id, limit)


class GetUnresolvedAlerts:
    def __init__(self, repo: IAlertRepository = None):
        self.repo = repo or AlertRepositoryImpl()

    def execute(self, device_id: int) -> List[Alert]:
        return self.repo.get_unresolved(device_id)


# ── Geofences ─────────────────────────────────────────────────────

class GetVehicleGeofences:
    def __init__(self, repo: IGeofenceRepository = None):
        self.repo = repo or GeofenceRepositoryImpl()

    def execute(self, vehicle_id: int) -> List[Geofence]:
        return self.repo.get_by_vehicle(vehicle_id)
