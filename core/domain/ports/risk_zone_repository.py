from abc import ABC, abstractmethod
from typing import List
from core.domain.entities.risk_zone import RiskZone


class IRiskZoneRepository(ABC):

    @abstractmethod
    def get_near_point(
        self, latitude: float, longitude: float, radius_meters: float = 500
    ) -> List[RiskZone]:
        """Uses PostGIS ST_DWithin to find risk zones near a point."""
        pass
