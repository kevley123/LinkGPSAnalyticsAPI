from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.entities.geofence import Geofence


class IGeofenceRepository(ABC):

    @abstractmethod
    def get_by_vehicle(self, vehicle_id: int) -> List[Geofence]:
        pass

    @abstractmethod
    def get_by_id(self, geofence_id: int) -> Optional[Geofence]:
        pass

    @abstractmethod
    def check_point_in_geofence(
        self, geofence_id: int, latitude: float, longitude: float
    ) -> bool:
        """Uses PostGIS ST_Contains to check if point is inside geofence."""
        pass
